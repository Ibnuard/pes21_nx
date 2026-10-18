"""Remove enclosed rigid head surfaces before allocating the visible skin budget."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_fit_realface import vertex_weights


def exterior(obj,positions,folder):
    mesh=obj.data;mesh.calc_loop_triangles()
    triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
    loops=[tuple(t.loops) for t in mesh.loop_triangles]
    normals=[n.vector.copy() for n in mesh.corner_normals]
    tree=BVHTree.FromPolygons(positions,triangles,all_triangles=True)
    directions=[Vector((0,0,1)),Vector((0,0,-1))]
    for elevation in (-.65,0.,.65):
        for i in range(12):
            angle=i*math.pi/6
            directions.append(Vector((math.cos(angle),math.sin(angle),elevation)).normalized())
    weights=[vertex_weights(obj,v) for v in mesh.vertices]
    names=[g.name for g in obj.vertex_groups]
    keep=[]
    for index,triangle in enumerate(triangles):
        if any(positions[i].z<157 or set(weights[i])!={'sk_head'} for i in triangle):
            keep.append(index);continue
        a,b,c=(positions[i] for i in triangle)
        # Four interior samples include each corner's neighbourhood. Preserve
        # any face which can see outside the head in any sampled direction.
        samples=[(a+b+c)/3,(a*6+b+c)/8,(a+b*6+c)/8,(a+b+c*6)/8]
        visible=any(tree.ray_cast(p+d*.002,d,100)[0] is None for p in samples for d in directions)
        if visible:keep.append(index)
    proof=dict(before=len(triangles),after=len(keep),enclosed_triangles_removed=len(triangles)-len(keep),
               directions=len(directions),samples_per_triangle=4,neck_and_nonrigid_skin_preserved=True)
    if len(keep)!=len(triangles):
        new=bpy.data.meshes.new(mesh.name+'_exterior')
        new.from_pydata([v.co.copy() for v in mesh.vertices],[],[triangles[i] for i in keep]);new.update()
        layer=new.uv_layers.new(name='UVMap');transferred=[]
        for poly,old in zip(new.polygons,keep):
            poly.use_smooth=True
            for li,old_li in zip(poly.loop_indices,loops[old]):
                layer.data[li].uv=mesh.uv_layers[0].data[old_li].uv
                transferred.append(normals[old_li])
        for material in mesh.materials:new.materials.append(material)
        new.normals_split_custom_set(transferred)
        obj.data=new;obj.vertex_groups.clear()
        groups={name:obj.vertex_groups.new(name=name) for name in names}
        for i,values in enumerate(weights):
            for name,value in values.items():groups[name].add([i],value,'REPLACE')
    Path(folder,'skin-exterior.json').write_text(json.dumps(proof,indent=2))
    return proof
