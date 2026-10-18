"""Select original adjacent hair triangles under a strict offline budget.

No source vertex, weight, UV or shading normal is collapsed. Visibility scores
prefer the actual outside hairstyle; sparse native-style cards need an opaque
source-derived scalp undercoat and still require composite visual review.
"""
import numpy as np


def opaque_atlas_slot(size, occupied):
    """Use the free scalp tile without moving existing skin/eye UVs."""
    if size not in (128, 256):
        raise ValueError('Native opaque atlas must be 128 or 256 pixels')
    destination = np.asarray([[196, 4], [252, 188]]) * size // 256
    for tile in occupied.values():
        a, b = np.asarray(tile['destination_bounds'])
        if np.all(destination[0] < b + 2) and np.all(destination[1] > a - 2):
            raise ValueError('Opaque hair base overlaps the existing face/eye atlas')
    return destination


def inset_bulk(points, distance):
    """Undo bounded voxel dilation on scalp bulk, never on facial anatomy."""
    if not 0 <= distance <= .45:
        raise ValueError('Opaque scalp inset must stay within 0..0.45 cm')
    points = np.asarray(points, dtype=float)
    radial = points - [0., 4., 173.]
    length = np.linalg.norm(radial, axis=1, keepdims=True)
    if np.any(length < 1.):
        raise ValueError('Opaque scalp has a vertex inside the head centre')
    return points - radial / length * distance


def fit_bulk(points, triangles, source, texture, skin, budget):
    """Select a small inward correction using the unchanged composite gate.

    Source cards are included in the comparison, exactly as in final auditing.
    This compensates sampled-volume inflation, not missing source hair.
    """
    import realface_mobile_geometry as gm
    scalp = scalp_triangles(source[0], source[1])
    frames, _ = gm.audit(*source, texture[:, :, 3], skin=skin)
    for frame in frames:
        visible = frame['front'] >= 0
        discard = visible.copy(); discard[visible] = ~scalp[frame['front'][visible]]
        frame['front'][discard] = -1; frame['mask'] = frame['front'] >= 0
    selected, _ = select_cards(source[1], frames, budget, scalp)
    reference, _ = gm.audit(source[0], source[1][scalp], source[2][scalp], texture[:, :, 3], skin=skin)
    cards, _ = gm.audit(source[0], source[1][selected], source[2][selected], texture[:, :, 3], reference=reference)
    trials = []; best = None
    for distance in (0., .15, .30, .45):
        candidate = inset_bulk(points, distance); combined = []
        for basis, original, detail in zip(gm.views(), reference, cards):
            bulk = gm.raster(candidate, triangles, np.zeros((len(triangles), 3, 2)), np.ones((1, 1)),
                             basis, original['bounds'], skin_depth=original['skin_depth'])
            combined.append(dict(detail, mask=detail['mask'] | bulk['mask'],
                                 cards=detail['cards'] + bulk['cards'], opaque=detail['opaque'] + bulk['opaque']))
        proof = gm.compare(reference, combined)
        trials.append(dict(inset_cm=distance, projection=proof))
        rank = (composite_ok(proof), proof['silhouette_iou_min'], proof['silhouette_iou_mean'], -distance)
        if best is None or rank > best[0]: best = (rank, candidate, distance)
        if composite_ok(proof): break
    return best[1], dict(selected_inset_cm=best[2], maximum_inset_cm=.45, trials=trials,
                         original_face_untouched=True, topology_unchanged=True)


def composite_ok(proof):
    """Geometry gate only; passing it never grants appearance approval."""
    return bool(proof and proof.get('views')==13 and
        proof.get('silhouette_iou_min',0)>=.80 and proof.get('silhouette_iou_mean',0)>=.85 and
        proof.get('missing_coverage_max',1)<=.15)


def scalp_triangles(positions,triangles):
    """Separate facial hair without cutting long scalp hair at a height plane.

    Native-like opaque facial hair belongs in the face colour. Long locks can
    reach below the neck, so connected source shape takes priority over Z.
    """
    p=np.asarray(positions);tri=np.asarray(triangles,dtype=int)
    aliases={};keys=[];parent=[]
    for point in p:
        key=tuple(np.round(point,4))
        if key not in aliases:aliases[key]=len(parent);parent.append(len(parent))
        keys.append(aliases[key])
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for t in tri:
        a,b,c=[root(keys[int(v)]) for v in t];parent[b]=a;parent[c]=a
    groups={}
    for i,t in enumerate(tri):groups.setdefault(root(keys[int(t[0])]),[]).append(i)
    keep=np.ones(len(tri),bool);separate_beard=False
    for ids in groups.values():
        points=p[tri[ids]].reshape(-1,3);lo=points.min(axis=0);hi=points.max(axis=0)
        beard=hi[2]<169 and lo[1]>5 and np.abs(points[:,0]).max()<9
        brow=hi[2]<175 and lo[2]>168 and hi[2]-lo[2]<4 and lo[1]>6 and np.abs(points[:,0]).max()<9
        if beard or brow:keep[ids]=False
        separate_beard|=beard
    if separate_beard:
        centers=p[tri].mean(axis=1)
        keep&=~((centers[:,2]<168)&(centers[:,1]>6)&(np.abs(centers[:,0])<6.5))
    return keep


def card_groups(triangles):
    """Pair adjacent source triangles; never connect coincident UV/weight seams."""
    tri=np.asarray(triangles,dtype=int);edges={};adj=[set() for _ in tri]
    for i,face in enumerate(tri):
        for a,b in zip(face,np.roll(face,1)):
            edge=tuple(sorted((int(a),int(b))))
            for j in edges.get(edge,[]):adj[i].add(j);adj[j].add(i)
            edges.setdefault(edge,[]).append(i)
    pending=set(range(len(tri)));groups=[]
    while pending:
        i=min(pending);pending.remove(i)
        candidates=adj[i]&pending
        if candidates:
            j=min(candidates);pending.remove(j);groups.append((i,j))
        else:groups.append((i,))
    return groups


def select_cards(triangles,frames,budget,eligible=None):
    if not isinstance(budget,int) or budget<1 or budget>2000:
        raise ValueError('Card budget must fit the complete-head ceiling')
    groups=card_groups(triangles);weights=np.zeros(len(triangles),float)
    eligible=np.ones(len(triangles),bool) if eligible is None else np.asarray(eligible,dtype=bool)
    if eligible.shape!=(len(triangles),):raise ValueError('Card eligibility count differs from source')
    counts=np.zeros(len(triangles),int)
    for frame in frames:
        front=np.asarray(frame['front']);visible=front>=0
        # Give every angle equal weight. Exterior outline texels carry extra
        # weight because the opaque scalp cannot replace their silhouette.
        padded=np.pad(visible,1)
        interior=np.logical_and.reduce([padded[y:y+len(front),x:x+front.shape[1]]
                                        for y,x in ((1,0),(1,2),(0,1),(2,1))])
        score=np.where(visible&~interior,5.,1.)/max(visible.sum(),1)
        weights+=np.bincount(front[visible],weights=score[visible],minlength=len(triangles))
        counts+=np.bincount(front[visible],minlength=len(triangles))
    order=sorted(groups,key=lambda ids:(-float(weights[list(ids)].sum())/len(ids),ids))
    selected=[];remaining=budget
    for ids in order:
        if len(ids)<=remaining and eligible[list(ids)].all() and weights[list(ids)].sum()>0:
            selected.extend(ids);remaining-=len(ids)
    chosen=np.asarray(sorted(selected),dtype=int)
    return chosen,dict(source_triangles=len(triangles),selected_triangles=len(chosen),budget=budget,
        source_visible_pixels=int(counts.sum()),selected_front_pixels=int(counts[chosen].sum()),
        original_geometry_uv_weights_normals=True,visual_approval=False)
