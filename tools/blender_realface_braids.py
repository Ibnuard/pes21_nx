"""Retopologize repeated braid cores without flattening them into a scalp cap.

Detect paired opaque cores and translucent fuzz from the same source. Use
those source rings for the silhouette and the core UVs for color. Native
head binding, two runtime sections and the complete-head budget stay fixed.
"""
import json,sys,shutil
from pathlib import Path
import numpy as np,bpy,bmesh
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_fit_realface import runtime_matrix

def build(obj,p,t,uv,alpha,native,cooked,job,target):
 lookup={};parent=[];weld=[]
 for point in p:
  k=tuple(np.round(point,4))
  if k not in lookup:lookup[k]=len(parent);parent.append(len(parent))
  weld.append(lookup[k])
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for tri in t:
  a,b,c=[root(weld[x]) for x in tri];parent[b]=a;parent[c]=a
 parts={}
 for i,tri in enumerate(t):parts.setdefault(root(weld[tri[0]]),[]).append(i)
 components=[]
 for ids in parts.values():
  q=p[t[ids]].reshape((-1,3));coord=uv[ids].mean(axis=1)%1;values=alpha[(coord[:,1]*len(alpha)).astype(int),(coord[:,0]*alpha.shape[1]).astype(int)]
  components.append(dict(ids=ids,alpha=float(values.mean()),lo=q.min(axis=0),hi=q.max(axis=0),points=q,uv=uv[ids].reshape((-1,2))))
 cores=[c for c in components if c['alpha']>.85 and len(c['ids'])>=200];drop=[]
 if not cores:raise ValueError('No structured opaque braid cores')
 for c in components:
  if c['alpha']>=.5 or len(c['ids'])<200:continue
  matches=[d for d in cores if np.max(np.abs(d['lo']-c['lo']))<.65 and np.max(np.abs(d['hi']-c['hi']))<.65]
  if matches:
   owner=min(matches,key=lambda d:np.linalg.norm(d['lo']-c['lo'])+np.linalg.norm(d['hi']-c['hi']));owner['envelope']=c;drop.extend(c['ids'])
 positions=[];coordinates=[];faces=[];proof=[];normals_world=[]
 for core in cores:
  envelope=core.get('envelope',core);q=envelope['points'];st=envelope['uv'];rings=[]
  source_surface=BVHTree.FromPolygons([Vector(point) for point in p],t[envelope['ids']].tolist(),all_triangles=True)
  for v in sorted(set(np.round(st[:,1],4))):
   ids=np.flatnonzero(np.abs(st[:,1]-v)<.000051);pts=np.unique(np.round(q[ids],4),axis=0)
   if len(pts)<3:continue
   center=pts.mean(axis=0);radius=np.linalg.norm(pts-center,axis=1)
   rings.append((float(v),center,float(np.quantile(radius,.9)),pts-center))
  if len(rings)<8:raise ValueError('Structured braid has insufficient longitudinal rings')
  v=np.array([r[0] for r in rings]);centers=np.array([r[1] for r in rings]);radii=np.array([r[2] for r in rings]);length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(centers,axis=0),axis=1))]
  if length[-1]<1:raise ValueError('Degenerate braid spine')
  count=5;sides=4;knots=np.linspace(0,length[-1],count)
  cc=np.array([np.interp(knots,length,centers[:,a]) for a in range(3)]).T;rr=np.interp(knots,length,radii);vv=np.interp(knots,length,v)
  start=len(positions);basis=None;low=core['uv'].min(axis=0);high=core['uv'].max(axis=0)
  for i,(center,radius,vo) in enumerate(zip(cc,rr,vv)):
   tangent=cc[min(i+1,count-1)]-cc[max(i-1,0)];tangent/=np.linalg.norm(tangent)
   if basis is None:
    z=np.array([1.,0.,0.]) if abs(tangent[0])<.8 else np.array([0.,1.,0.]);basis=z-tangent*np.dot(z,tangent)
   else:basis=basis-tangent*np.dot(basis,tangent)
   basis/=np.linalg.norm(basis);other=np.cross(tangent,basis)
   angles=np.arange(sides)*2*np.pi/sides;normals=np.array([np.cos(angles),np.sin(angles)]).T
   frame=np.array([basis,other]);support=np.array([[np.max((r[3]@frame.T)@n) for n in normals] for r in rings])
   extents=np.array([np.interp(vo,v,support[:,j]) for j in range(sides)])
   polygon=[np.linalg.solve(normals[[j,(j+1)%sides]],extents[[j,(j+1)%sides]]) for j in range(sides)]
   covariance=np.array([frame@(r[3].T@r[3]/len(r[3]))@frame.T for r in rings])
   ellipse=np.array([[np.interp(vo,v,covariance[:,a,b]) for b in range(2)] for a in range(2)])
   normal_matrix=np.linalg.inv(ellipse+np.eye(2)*.0001)
   for j in range(sides+1):
    radial=polygon[j%sides];point=center+radial[0]*basis+radial[1]*other
    # The broad root fans follow scalp curvature; flattening their source
    # ring to one plane would leave a rectangular lip above the crown.
    if i==count-1:
     hit,_,_,distance=source_surface.find_nearest(Vector(point))
     if hit is not None and distance<=1.2:point=.65*point+.35*np.asarray(hit)
    positions.append(point);coordinates.append((low[0]+(high[0]-low[0])*j/sides,vo))
    normal=frame.T@(normal_matrix@radial);normal/=max(np.linalg.norm(normal),1e-10);normals_world.append(normal)
  for i in range(count-1):
   for j in range(sides):
    a=start+i*(sides+1)+j;b=a+1;c=a+sides+1;d=c+1;faces.extend(((a,b,c),(b,d,c)))
  proof.append(dict(source_triangles=len(core['ids']),rings=len(rings),length_cm=float(length[-1]),radius_max_cm=float(radii.max())))
 used=set(drop)|{i for c in cores for i in c['ids']};remain=[i for i in range(len(t)) if i not in used]
 # Retain non-braid accessories/goatee as a separate temporary surface and
 # spend the remaining budget there; they do not change the strand spines.
 source_mesh=obj.data;extra=bpy.data.meshes.new('extras');ep=[];eu=[];ef=[]
 for index in remain:
  start=len(ep);ep.extend(p[t[index]]);eu.extend(uv[index]);ef.append((start,start+1,start+2))
 # Input triangles retain FBX-space winding. Normalize them before the
 # accessory collapse; the new braid surfaces already face outwards.
 reflected=runtime_matrix(obj,{'sk_head':1.},native,cooked).determinant()<0
 extra.from_pydata(ep,[],[tuple(reversed(f)) for f in ef] if reflected else ef);extra.update();layer=extra.uv_layers.new(name='UVMap')
 for poly in extra.polygons:
  for vi,li in zip(poly.vertices,poly.loop_indices):layer.data[li].uv=eu[vi]
 obj.data=extra;obj.vertex_groups.clear();obj.vertex_groups.new(name='sk_head').add(list(range(len(ep))),1.,'REPLACE')
 bm=bmesh.new();bm.from_mesh(extra);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001);bm.to_mesh(extra);bm.free();extra.calc_loop_triangles()
 budget=target-len(faces)
 if budget<20:raise ValueError('Braid recipe requires more hair allocation')
 mod=obj.modifiers.new('Accessory budget','DECIMATE');mod.ratio=min(1,budget/max(len(extra.loop_triangles),1));mod.use_collapse_triangulate=True
 bpy.context.view_layer.objects.active=obj
 while obj.modifiers.find(mod.name)>0:bpy.ops.object.modifier_move_up(modifier=mod.name)
 bpy.ops.object.modifier_apply(modifier=mod.name);obj.data.calc_loop_triangles()
 for tri in obj.data.loop_triangles:
  start=len(positions);positions.extend(obj.data.vertices[i].co[:] for i in tri.vertices);coordinates.extend(obj.data.uv_layers[0].data[i].uv[:] for i in tri.loops);normals_world.extend(obj.data.corner_normals[i].vector[:] for i in tri.loops);faces.append((start,start+1,start+2))
 mesh=bpy.data.meshes.new('structured_braids');mesh.from_pydata(positions,[],faces);mesh.update();layer=mesh.uv_layers.new(name='UVMap')
 for poly in mesh.polygons:
  poly.use_smooth=True
  for vi,li in zip(poly.vertices,poly.loop_indices):layer.data[li].uv=coordinates[vi]
 for mat in source_mesh.materials:mesh.materials.append(mat)
 obj.data=mesh;obj.vertex_groups.clear();obj.vertex_groups.new(name='sk_head').add(list(range(len(positions))),1.,'REPLACE');inverse=runtime_matrix(obj,{'sk_head':1.},native,cooked).inverted()
 from blender_realface_hair_reduce import from_native_surface
 from_native_surface(mesh,inverse)
 normal_transform=inverse.inverted().transposed().to_3x3()
 mesh.normals_split_custom_set([(normal_transform@Vector(normals_world[loop.vertex_index])).normalized() for loop in mesh.loops])
 return dict(mode='structured_braid_cores',cores=len(cores),fuzz_triangles_removed=len(drop),spines=proof)


def run(job):
 from blender_export_ue_fbx import rig_globals
 from blender_realface_lite import reduce_part,export,normalized,surface,quality
 from blender_realface_mobile import geometry,pixels,source_views,finish_hair
 folder=Path(job['folder']);profile=job['source_profile']
 native=rig_globals(json.loads(Path(job['native_rig']).read_text()));cooked=rig_globals(json.loads(Path(job['cooked_rig']).read_text()))
 face=reduce_part(job,'face',native,cooked)
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
 copied=folder/'input-hair.fbx'
 if not copied.exists():shutil.copy2(profile['hair_fbx'],copied)
 bpy.ops.import_scene.fbx(filepath=str(copied),use_anim=False)
 arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
 if len(arms)!=1 or set(b.name for b in arms[0].data.bones)!=set(native):raise ValueError('Braid input rig differs from native skeleton')
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];allowed=set(map(normalized,profile['hair_materials']))
 if any({normalized(m.name) for m in o.data.materials}-allowed for o in meshes):raise ValueError('Unclassified braid input material')
 bpy.ops.object.select_all(action='DESELECT')
 for obj in meshes:obj.select_set(True)
 bpy.context.view_layer.objects.active=meshes[0]
 if len(meshes)>1:bpy.ops.object.join()
 obj=bpy.context.object;obj.name='lite_hair';obj.data.materials.clear();obj.data.materials.append(bpy.data.materials.new('lite_hair'))
 for poly in obj.data.polygons:poly.material_index=0
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
 data=geometry(obj,native,cooked);alpha=pixels(profile['hair_texture'])[:,:,3]
 before,_=source_views(data,alpha,job);old_points,old_faces=surface(obj,native,cooked)
 from blender_realface_league_worker import remaining_hair_budget
 hair_budget=remaining_hair_budget(job['budgets'],face['total'])['hair']
 method=build(obj,*data,alpha,native,cooked,job,hair_budget)
 result=finish_hair(obj,job,native,cooked,(before,alpha,method['fuzz_triangles_removed'],method))
 obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
 if count>hair_budget:raise ValueError('Braid retopology exceeds its allocation')
 metric=dict(before=len(data[1]),after=count,vertices=len(obj.data.vertices),error=quality(old_points,old_faces,obj,native,cooked),exterior=result)
 (folder/'hair-hair-metrics.json').write_text(json.dumps(metric,indent=2))
 export(folder/'hair.fbx',arms[0])
 hair=dict(roles=dict(hair=metric),bones=list(native),total=count,sections=1,fbx=str(folder/'hair.fbx'))
 total=face['total']+count
 if total>job['budgets']['head_cap']:raise ValueError('Braid complete head exceeds mobile ceiling')
 report=dict(face=face,hair=hair,base_id=job['base_id'],native_player_id=job['native_player_id'],total_triangles=total,hardware_accepted=False)
 (folder/'simplification.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PESNX_REALFACE_LITE_PREPARED',job['base_id'],total,flush=True)


if __name__=='__main__':run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
