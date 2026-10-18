"""Source-derived scalp and facial-hair shells with separate radial centers.

A beard must not share the scalp's radial origin: that creates lateral fins.
Both regions still use one masked atlas and the original native head bone.
The angular crop allocates texels to occupied latitude instead of wasting
most of a small facial-hair tile on empty polar directions.
"""
import json,math,hashlib
from pathlib import Path
import inspect
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_fit_realface import runtime_matrix

def build(obj,job,native,cooked):
 from blender_realface_mobile import geometry,pixels
 from realface_mobile_geometry import compact_hair_mask
 p,tri,uv=geometry(obj,native,cooked);tex=pixels(job['source_profile']['hair_texture']);h,w=tex.shape[:2]
 detail=bool(job['budgets'].get('detail_shell'));size=256 if detail else 128
 if detail:
  from blender_realface_source_quality import capture_normals
  _,_,source_normals=capture_normals(obj,native,cooked)
 # Connected source cards entirely below the eye and in front of the jaw.
 keys={};parent=[];weld=[]
 for v in p:
  key=tuple(np.round(v,4))
  if key not in keys:keys[key]=len(parent);parent.append(len(parent))
  weld.append(keys[key])
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for t in tri:
  a,b,c=[root(weld[i]) for i in t];parent[b]=a;parent[c]=a
 components={}
 for i,t in enumerate(tri):components.setdefault(root(weld[t[0]]),[]).append(i)
 beard=[]
 for ids in components.values():
  pts=p[tri[ids]].reshape((-1,3))
  if pts[:,2].max()<169 and pts[:,1].min()>5 and np.abs(pts[:,0]).max()<9:beard.extend(ids)
 mask=np.zeros(len(tri),bool);mask[beard]=True
 # Some exporters weld the jaw cards to the scalp. A component-only split
 # then treats the beard as a very long fringe and fills the face between
 # them. Refine that split only when a separate facial-hair region exists;
 # side/back long hair stays with the scalp.
 if beard and job['budgets'].get('solid_scalp'):
  centers=p[tri].mean(axis=1)
  mask|=(centers[:,2]<168)&(centers[:,1]>6)&(np.abs(centers[:,0])<6.5)
  beard=np.flatnonzero(mask).tolist()
 regions=[('scalp',np.flatnonzero(~mask),size*3//4),('beard',np.flatnonzero(mask),size//4)] if beard else [('scalp',np.arange(len(tri)),size)]
 atlas=np.zeros((size,size,4),np.float32);verts=[];coords=[];faces=[];proof=[];ybase=0
 for name,ids,height in regions:
  tt=tri[ids];uu=uv[ids];q=p[tt].reshape((-1,3));lo,hi=np.percentile(q,[.5,99.5],axis=0)
  center=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,173. if name=='scalp' else 162.5))
  if name=='beard':center.y=6.5
  delta=q-np.asarray(center);polar=np.arccos(np.clip(delta[:,2]/np.maximum(np.linalg.norm(delta,axis=1),.0001),-1,1))/math.pi
  vmin=max(0.,float(polar.min())-.02);vmax=min(1.,float(polar.max())+.02)
  tree=BVHTree.FromPolygons([Vector(v) for v in p],tt.tolist(),all_triangles=True)
  def direction(u,v):
   a=u*math.tau;b=(vmin+v*(vmax-vmin))*math.pi
   return Vector((math.sin(b)*math.cos(a),math.sin(b)*math.sin(a),math.cos(b)))
  def sample(ray):
   origin=center+ray*42
   for _ in range(64):
    remain=(origin-center).dot(ray)
    if remain<=.25:return None
    hit,_,idx,_=tree.ray_cast(origin,-ray,remain-.25)
    if idx is None:return None
    a,b,c=[Vector(v) for v in p[tt[idx]]];e0=b-a;e1=c-a;e2=hit-a
    aa=e0.dot(e0);ab=e0.dot(e1);bb=e1.dot(e1);den=aa*bb-ab*ab
    if abs(den)>1e-12:
     u=(bb*e2.dot(e0)-ab*e2.dot(e1))/den;v=(aa*e2.dot(e1)-ab*e2.dot(e0))/den
     uv0=np.array([1-u-v,u,v])@uu[idx];x=uv0[0]*w-.5;y=uv0[1]*h-.5
     ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
     color=tex[iy%h,ix%w]*(1-fx)*(1-fy)+tex[iy%h,(ix+1)%w]*fx*(1-fy)+tex[(iy+1)%h,ix%w]*(1-fx)*fy+tex[(iy+1)%h,(ix+1)%w]*fx*fy
     if color[3]>=.333:
      if detail:
       # Store modest source micro-shading in the existing colour texture.
       # This retains curls that the mobile triangle budget cannot represent
       # without introducing another material, sampler or runtime operation.
       normal=Vector(np.array([1-u-v,u,v])@source_normals[ids[idx]]).normalized()
       if normal.dot(ray)<0:normal=-normal
       lights=[Vector((.6,.8,1)).normalized(),Vector((-.6,.6,.8)).normalized()]
       shading=lambda n:.55+sum(max(0.,n.dot(light)) for light in lights)*.225
       factor=min(1.25,max(.65,shading(normal)/shading(ray)))
       color=color.copy();color[:3]*=factor
      return (hit-center).length,color
    origin=hit-ray*.002
   return None
  tile=np.zeros((height,size,4),np.float32);radii=np.zeros((height,size),np.float32)
  digest=hashlib.sha256((inspect.getsource(direction)+inspect.getsource(sample)).encode())
  for data in (p,tt,uu,tex,np.asarray(center),np.array([vmin,vmax,height,size,detail])):digest.update(data.tobytes())
  if detail:digest.update(source_normals.tobytes())
  cache=Path(job['folder']).parent/'hair-bakes'/(digest.hexdigest()+'.npz')
  if cache.exists():
   with np.load(cache,allow_pickle=False) as stored:radii=stored['radii'];tile=stored['atlas']
  else:
   for y in range(height):
    for x in range(size):
     value=sample(direction((x+.5)/size,(y+.5)/height))
     if value:radii[y,x],tile[y,x]=value
   cache.parent.mkdir(parents=True,exist_ok=True)
   temp=cache.with_name(cache.stem+'-'+str(job['base_id'])+'.tmp.npz')
   np.savez_compressed(temp,radii=radii,atlas=tile);temp.replace(cache)
  if np.count_nonzero(radii)<16:raise ValueError('Hair region has insufficient visible coverage')
  if name=='scalp':
   tile[:,:,3]=compact_hair_mask(tile[:,:,3],radius=2)
   if job['budgets'].get('solid_scalp'):
    from realface_hair_envelope import solid_scalp_mask
    tile[:,:,3]=solid_scalp_mask(tile[:,:,3])
  known=radii>0;rgb=tile[:,:,:3].copy()
  for _ in range(128 if job['budgets'].get('solid_scalp') and name=='scalp' else 4):
   sums=np.zeros_like(rgb);counts=np.zeros_like(radii)
   for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
    v=np.roll(known,(dy,dx),(0,1));sums+=np.roll(rgb,(dy,dx),(0,1))*v[:,:,None];counts+=v
   fill=~known&(counts>0);rgb[fill]=sums[fill]/counts[fill,None];known|=fill
   if known.all():break
  tile[:,:,:3]=rgb;atlas[ybase:ybase+height]=tile
  segments=64 if detail else 32;rings=(32 if name=='scalp' else 24) if detail else (16 if name=='scalp' else 12);start=len(verts)
  for row in range(rings+1):
   v=np.clip(row/rings,.001,.999)
   for col in range(segments+1):
    u=col/segments;ray=direction(u,v);hit=sample(ray)
    if hit:radius=hit[0]
    else:
     x=int(u*size)%size;y=min(int(v*height),height-1)
     near=[radii[min(max(y+dy,0),height-1),(x+dx)%size] for dy in range(-4,5) for dx in range(-4,5)]
     live=[r for r in near if r>0];radius=float(np.median(live)) if live else 8.
    verts.append(center+ray*radius);coords.append((u,(ybase+v*height)/size))
  for row in range(rings):
   for col in range(segments):
    x0=int(col/segments*size);x1=min(int((col+1)/segments*size)+1,size);y0=int(row/rings*height);y1=min(int((row+1)/rings*height)+1,height)
    if not np.any(tile[y0:y1,x0:x1,3]>=.333):continue
    a=start+row*(segments+1)+col;b=a+1;c=a+segments+1;d=c+1;faces.extend(((a,c,b),(b,c,d)))
  proof.append(dict(region=name,source_triangles=len(ids),center=list(center),polar_bounds=[vmin,vmax]));ybase+=height
 image=bpy.data.images.new('mobile_hair_shell',width=size,height=size,alpha=True);image.alpha_mode='CHANNEL_PACKED'
 image.pixels.foreach_set(atlas.ravel());image.filepath_raw=str(Path(job['folder'],'hair-shell.png'));image.file_format='PNG';image.save()
 mesh=bpy.data.meshes.new('mobile_regions');mesh.from_pydata(verts,[],faces);mesh.update();layer=mesh.uv_layers.new(name='UVMap')
 for poly in mesh.polygons:
  poly.use_smooth=True
  for vi,li in zip(poly.vertices,poly.loop_indices):layer.data[li].uv=coords[vi]
 for mat in obj.data.materials:mesh.materials.append(mat)
 obj.data=mesh;obj.vertex_groups.clear();obj.vertex_groups.new(name='sk_head').add(list(range(len(verts))),1.,'REPLACE')
 inverse=runtime_matrix(obj,{'sk_head':1.},native,cooked).inverted()
 from blender_realface_hair_reduce import from_native_surface
 from_native_surface(mesh,inverse)
 return atlas[:,:,3],dict(mode='split_radial_surface',regions=proof,texture_size=size,bone='sk_head',source_layers_traced_offline=True,
                         solid_scalp=bool(job['budgets'].get('solid_scalp')))
