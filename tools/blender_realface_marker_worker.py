"""Seam-safe conversion after visibility-checked microscopic marker cleanup."""
import json
from pathlib import Path
import runpy
import sys

import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import blender_meshopt
from realface_skin_markers import marker_triangles
from realface_mobile_geometry import views, raster
from realface_fast_raster import load

original_reduce = blender_meshopt.reduce


def reduce(obj, positions, target, role, job):
    if role != 'skin' or not job['budgets'].get('skin_marker_cleanup'):
        return original_reduce(obj, positions, target, role, job)
    mesh=obj.data;mesh.calc_loop_triangles()
    triangles=np.asarray([t.vertices[:] for t in mesh.loop_triangles])
    loops=[t.loops[:] for t in mesh.loop_triangles]
    weights=[tuple(sorted((g.group,g.weight) for g in v.groups)) for v in mesh.vertices]
    remove,clusters=marker_triangles(positions,triangles,weights)
    proof=dict(removed_triangles=len(remove),clusters=clusters,positions_moved=False,
               surface_limits_unchanged=True,visibility_views=0)
    if remove:
        keep=np.asarray(sorted(set(range(len(triangles)))-set(remove)))
        active=raster if not job.get('fast_raster') else load(job['fast_raster'])
        points=np.asarray(positions)
        for basis in views():
            before=active(points,triangles,np.zeros((len(triangles),3,2)),np.ones((1,1)),basis,size=128)
            after=active(points,triangles[keep],np.zeros((len(keep),3,2)),np.ones((1,1)),basis,
                         bounds=before['bounds'],size=128)
            if not np.array_equal(before['mask'],after['mask']):
                raise ValueError('Microscopic marker cleanup changes visible skin coverage')
            mask=before['mask']
            if np.max(np.abs(before['depth'][mask]-after['depth'][mask]),initial=0)>1e-5:
                raise ValueError('Microscopic marker cleanup changes visible skin depth')
            proof['visibility_views']+=1
        normals=[n.vector.copy() for n in mesh.corner_normals]
        new=bpy.data.meshes.new(mesh.name+'_without_hidden_markers')
        new.from_pydata([v.co.copy() for v in mesh.vertices],[],triangles[keep].tolist());new.update()
        layer=new.uv_layers.new(name='UVMap');transferred=[]
        for polygon,index in zip(new.polygons,keep):
            polygon.use_smooth=True
            for li,old in zip(polygon.loop_indices,loops[index]):
                layer.data[li].uv=mesh.uv_layers[0].data[old].uv
                transferred.append(normals[old])
        for material in mesh.materials:new.materials.append(material)
        new.normals_split_custom_set(transferred)
        names=[g.name for g in obj.vertex_groups]
        obj.data=new;obj.vertex_groups.clear()
        groups=[obj.vertex_groups.new(name=name) for name in names]
        for index,values in enumerate(weights):
            for group,weight in values:groups[group].add([index],weight,'REPLACE')
    (Path(job['folder'])/'skin-marker-cleanup.json').write_text(json.dumps(proof,indent=2))
    return original_reduce(obj,positions,target,role,job)


blender_meshopt.reduce=reduce
runpy.run_path(str(Path(__file__).with_name('blender_realface_seam_worker.py')),run_name='__main__')
