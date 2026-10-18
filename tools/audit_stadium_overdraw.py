"""Blender ray-sample audit of foreground fragments avoided by vertex culling.

Counts sampled geometric intersections, NOT GPU time or FPS. Checks that no
new vertex rejection removes a fragment visible under the exact pixel policy.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stadium_material_policy import camera_box_hidden,camera_visible

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--profile',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--near-field',action='store_true',help='Also sample low near-touchline cameras at midfield and both goals')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
profile=json.loads(a.profile.read_text())
bpy.ops.wm.open_mainfile(filepath=str(Path(profile['fbx']).with_suffix('.blend')))
obj=bpy.data.objects[profile['key']+'Shell'];mesh=obj.data
tree=BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())
def ue(p):return (p[0]*100,-p[1]*100,p[2]*100)
bounds=[]
if profile.get('vertex_camera_cull'):
    xy,ze,yz=[mesh.uv_layers[i].data for i in (2,3,4)]
    for face in mesh.polygons:
        i=face.loop_start
        bounds.append(((xy[i].uv.x*32768,(1-xy[i].uv.y)*32768,ze[i].uv.x*32768),
                       ((1-ze[i].uv.y)*32768,yz[i].uv.x*32768,(1-yz[i].uv.y)*32768)))
reports=[]
views=[('near',(0,-68,28),(0,-20,0)),('far',(0,-16,28),(0,32,0))]
if a.near_field:
    views += [('near-x%d-z%d'%(x,z),(x,-60,z),(x,-27,0)) for x in (0,-42,42) for z in (10,18,28)]
for name,position,target in views:
    camera=Vector(position);forward=(Vector(target)-camera).normalized()
    right=forward.cross(Vector((0,0,1))).normalized();up=right.cross(forward).normalized()
    hidden=[camera_box_hidden(c,h,ue(camera)) for c,h in bounds] if bounds else [False]*len(mesh.polygons)
    stats=dict(view=name,rays=96*54,intersections=0,source_backfaces=0,fragment_cutaways=0,vertex_cutaways=0,visible_removed=0)
    for y in range(54):
        for x in range(96):
            direction=(forward+right*((x+.5)/96*2-1)*.6+up*((y+.5)/54*2-1)*.3375).normalized()
            origin=camera.copy();travelled=0
            for layer in range(256):
                point,normal,index,distance=tree.ray_cast(origin,direction,350-travelled)
                if index is None:break
                stats['intersections']+=1
                material=mesh.materials[mesh.polygons[index].material_index].name
                backface=not profile['material_policies'].get(material,{}).get('two_sided',True) and normal.dot(direction)>=0
                if backface:stats['source_backfaces']+=1
                else:
                    visible=camera_visible(ue(point),ue(camera))
                    stats['fragment_cutaways']+=not visible
                    if hidden[index]:
                        stats['vertex_cutaways']+=1
                        stats['visible_removed']+=visible
                origin=point+direction*.003;travelled=(origin-camera).length
                if travelled>=350:break
            else:raise RuntimeError('Ray did not progress')
    if stats['visible_removed']:raise RuntimeError('Unsafe camera cluster rejection: '+str(stats))
    stats['rgb_candidates_before_alpha']=stats['intersections']-stats['source_backfaces']-stats['vertex_cutaways']
    stats['camera_rejected_rgb_candidates']=stats['fragment_cutaways']-stats['vertex_cutaways']
    reports.append(stats)
a.output.write_text(json.dumps(dict(key=profile['key'],scope='geometric ray intersections; excludes alpha-texture tests; not a frame-time benchmark',views=reports),indent=2)+'\n')
print(json.dumps(reports))
