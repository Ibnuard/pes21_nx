"""Fit opaque eye depth against the player's actual skin before reduction."""
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_fit_realface import runtime_matrix,vertex_weights
from blender_realface_lite import points,normalized
from realface_eye_fit import sphere
from realface_eye_boundary import rim_variants
from realface_eye_enclosure import choose_depth


def aperture_cap(center,xs,zs,opening,skin_tree,eye_tree,positions,faces,source_uv,rim_clearance=.025,front_clearance=.03):
    """Keep the iris forward while tucking a small front patch under the lid.

    A whole spherical globe pushed backwards can leave a dark recessed eye.
    Only the visible anterior patch is needed behind an opaque mobile face.
    Its UVs come from ray hits on this player's original eye geometry.
    """
    vertices=[];uv=[];triangles=[];segments=16;rings=3
    def eye_hit(x,z):
        hit,_,index,_=eye_tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
        if hit is None:
            hit,_,index,_=eye_tree.find_nearest(Vector((x,center[1]+1.5,z)))
        a,b,c=(Vector(positions[i]) for i in faces[index]);e0=b-a;e1=c-a;q=hit-a
        aa=e0.dot(e0);ab=e0.dot(e1);bb=e1.dot(e1);den=aa*bb-ab*ab
        if abs(den)<1e-12:raise ValueError('Eye UV projection hit a degenerate face')
        u=(bb*q.dot(e0)-ab*q.dot(e1))/den;v=(aa*q.dot(e1)-ab*q.dot(e0))/den
        return hit,np.array([1-u-v,u,v])@source_uv[index]
    hit,coord=eye_hit(center[0],center[2]);vertices.append((center[0],hit.y-front_clearance,center[2]));uv.append(coord)
    for ring in range(1,rings+1):
        t=ring/rings
        for segment in range(segments):
            angle=segment*2*math.pi/segments;dx=math.cos(angle);dz=math.sin(angle)
            last=0.
            for radius in np.linspace(0,2.5,251):
                x=center[0]+radius*dx;z=center[2]+radius*dz
                xi=int(np.argmin(abs(xs-x)));zi=int(np.argmin(abs(zs-z)))
                if not opening[zi,xi]:break
                last=float(radius)
            if last<.15:raise ValueError('Pupil lies outside a usable eyelid aperture')
            # Overlap the hidden edge with skin; an inset cap would expose a
            # black crack between sclera and lid when viewed at an angle.
            radius=(last*.67 if ring==1 else last-.04 if ring==2 else last+.08)
            x=center[0]+radius*dx;z=center[2]+radius*dz
            original,coord=eye_hit(x,z)
            skin,_,_,_=skin_tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
            if skin is None:raise ValueError('Missing skin support at eyelid edge')
            # Two close rim rings follow the actual local skin depth, not a
            # broad spherical-to-edge interpolation which crosses oblique lids.
            y=original.y-front_clearance if ring==1 else skin.y-rim_clearance-(0 if ring==2 else .02)
            vertices.append((x,y,z));uv.append(coord)
    for i in range(segments):triangles.append((0,1+i,1+(i+1)%segments))
    for ring in range(rings-1):
        a=1+ring*segments;b=a+segments
        for i in range(segments):
            j=(i+1)%segments;triangles.extend(((a+i,b+i,a+j),(a+j,b+i,b+j)))
    # The front of the native head is +Y. A CCW fan in the X/Z plane
    # points toward -Y and makes the iris shade almost black. Face the cap
    # outwards; its near-lid folds keep the same consistent winding.
    return vertices,[tuple(reversed(face)) for face in triangles],uv


def clean(groups,job,native,cooked):
    if len(groups.get('eye',[]))!=1:raise ValueError('Eye cleanup needs one classified eye mesh')
    eye=groups['eye'][0];positions=np.array(points(eye,native,cooked));eye.data.calc_loop_triangles()
    inverse=runtime_matrix(eye,{'sk_head':1.},native,cooked).inverted()
    reflected=inverse.determinant()<0
    faces=[t.vertices[:] for t in eye.data.loop_triangles]
    source_uv=np.array([[eye.data.uv_layers[0].data[i].uv[:] for i in t.loops] for t in eye.data.loop_triangles])
    skin_points=[];skin_faces=[]
    for obj in groups.get('skin',[]):
        start=len(skin_points);skin_points.extend(points(obj,native,cooked));obj.data.calc_loop_triangles()
        skin_faces.extend(tuple(start+i for i in t.vertices) for t in obj.data.loop_triangles)
    skin_tree=BVHTree.FromPolygons(skin_points,skin_faces,all_triangles=True)
    reports=[];rims=[];rebuilt_points=[];rebuilt_faces=[];rebuilt_uv=[]
    for sign in (-1,1):
        ids=np.flatnonzero(positions[:,0]*sign>0)
        center,radius,rms=sphere(positions[ids])
        xs=np.linspace(center[0]-2.2,center[0]+2.2,147)
        zs=np.linspace(center[2]-2.,center[2]+2.,135)
        eye_tree=BVHTree.FromPolygons([Vector(p) for p in positions],faces,all_triangles=True)
        skin=np.full((len(zs),len(xs)),-100.);depth=np.full_like(skin,-np.inf)
        for zi,z in enumerate(zs):
            for xi,x in enumerate(xs):
                origin=Vector((x,40.,z));direction=Vector((0.,-1.,0.))
                a,_,_,_=skin_tree.ray_cast(origin,direction);b,_,_,_=eye_tree.ray_cast(origin,direction)
                if a is not None:skin[zi,xi]=a.y
                if b is not None:depth[zi,xi]=b.y
        variants=rim_variants(xs,zs,skin)
        attempts=[];result=None
        for variant in variants:
            rim=np.array(variant['bounds']);columns=sorted(set(rim[:,0]));lower=[];upper=[]
            for x in columns:
                values=rim[np.isclose(rim[:,0],x),2];lower.append(min(values)+.015);upper.append(max(values)-.015)
            bottom=np.interp(xs,columns,lower);top=np.interp(xs,columns,upper)
            opening=(zs[:,None]>=bottom)&(zs[:,None]<=top)&(xs>=columns[0])&(xs<=columns[-1])
            pupil=((xs[None,:]-center[0])**2+(zs[:,None]-center[2])**2)<.16**2
            try:
                choice,proof=choose_depth(depth,skin,opening,pupil)
                result=(choice,proof,rim,variant['name'],opening,pupil);break
            except ValueError as error:attempts.append(str(error))
        if result is None:
            reports.append(dict(side=sign,status='unresolved_preserved',attempts=attempts,variants=len(variants)))
            for fi,face in enumerate(faces):
                if all(i in ids for i in face):
                    start=len(rebuilt_points);rebuilt_points.extend(positions[list(face)]);rebuilt_uv.extend(source_uv[fi]);rebuilt_faces.append((start+2,start+1,start) if reflected else (start,start+1,start+2))
            continue
        choice,proof,rim,label,opening,pupil=result;shift=choice['depth_shift_cm'];rims.extend(rim.tolist())
        if shift>.05:
            for rim_clearance in (.025,.075,.15,.25,.4,.6):
                p,f,st=aperture_cap(center,xs,zs,opening,skin_tree,eye_tree,positions,faces,source_uv,rim_clearance)
                after_tree=BVHTree.FromPolygons([Vector(v) for v in p],f,all_triangles=True)
                visible=np.zeros_like(opening)
                for zi,z in enumerate(zs):
                    for xi,x in enumerate(xs):
                        hit,_,_,_=after_tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
                        if hit is not None:visible[zi,xi]=hit.y>skin[zi,xi]+.005
                spill=int((visible&~opening).sum());inside=int((visible&opening).sum())
                final=dict(spill_pixels=spill,inside_pixels=inside,spill_fraction=spill/max(spill+inside,1),
                           pupil_visible_fraction=float((visible&pupil).sum()/pupil.sum()),
                           interior_coverage=inside/max(choice['inside_pixels'],1),
                           raw_globe_coverage=inside/max(proof['before']['inside_pixels'],1))
                if final['spill_fraction']<=.03 and final['pupil_visible_fraction']>=.9 and final['interior_coverage']>=.75:break
            else:
                raise ValueError('Aperture eye cap failed visible-lid enclosure: '+str(final))
            start=len(rebuilt_points);rebuilt_points.extend(p);rebuilt_uv.extend(st)
            rebuilt_faces.extend(tuple(start+i for i in face) for face in f)
            proof['uniform_shift_candidate']=proof.pop('after');proof['after']=final
            proof.update(mode='visible_aperture_cap',front_clearance_cm=.03,rim_clearance_cm=rim_clearance,triangles=len(f))
        else:
            for fi,face in enumerate(faces):
                if all(i in ids for i in face):
                    start=len(rebuilt_points);rebuilt_points.extend(positions[list(face)]);rebuilt_uv.extend(source_uv[fi]);rebuilt_faces.append((start+2,start+1,start) if reflected else (start,start+1,start+2))
            proof['mode']='original_enclosed_eye'
        reports.append(dict(side=sign,status='adjusted' if shift>.05 else 'already_enclosed',measurement=label,**proof))
    mesh=bpy.data.meshes.new('mobile_eye_apertures');mesh.from_pydata(rebuilt_points,[],rebuilt_faces);mesh.update()
    layer=mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        poly.use_smooth=True
        for vi,li in zip(poly.vertices,poly.loop_indices):layer.data[li].uv=rebuilt_uv[vi]
    for material in eye.data.materials:mesh.materials.append(material)
    eye.data=mesh;eye.vertex_groups.clear();eye.vertex_groups.new(name='sk_head').add(list(range(len(rebuilt_points))),1.,'REPLACE')
    from blender_realface_hair_reduce import from_native_surface
    from_native_surface(mesh,inverse)
    job['eyelid_rim_points']=rims
    Path(job['folder'],'eye-enclosure.json').write_text(json.dumps(dict(eyes=reports,skin_geometry_changed=False),indent=2))
    return reports
