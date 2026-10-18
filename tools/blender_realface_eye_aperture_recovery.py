"""Fit a source-textured eye cap directly to a measured lid opening.

A viable uniform shift of the entire original globe is not required. The
actual cap must independently enclose its rim and retain the original pupil.
This optional policy never moves the skin or swaps an eye texture.
"""
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from blender_fit_realface import runtime_matrix
from blender_realface_mobile import geometry
from blender_realface_eye_cleanup import aperture_cap
from blender_realface_hair_reduce import from_native_surface
from realface_eye_boundary import rim_variants
from realface_eye_fit import sphere


def clean(groups,job,native,cooked):
    import realface_mobile_geometry as checks
    if len(groups.get('eye',[]))!=1:raise ValueError('Eye cap requires one classified source eye mesh')
    eye=groups['eye'][0];p,t,uv=geometry(eye,native,cooked)
    eye_tree=BVHTree.FromPolygons([Vector(v) for v in p],t.tolist(),all_triangles=True)
    skin=[];faces=[]
    for obj in groups.get('skin',[]):
        vertices,tri,_=geometry(obj,native,cooked);faces.extend(tri+len(skin));skin.extend(vertices)
    skin=np.asarray(skin);faces=np.asarray(faces)
    tree=BVHTree.FromPolygons([Vector(v) for v in skin],faces.tolist(),all_triangles=True)
    basis=np.array([[1,0,0],[0,0,1],[0,1,0]])
    # Orbital measurement expects 0.025..0.08 cm between vertical samples.
    # Four centimetres / 135 keeps the existing source-scan contract.
    points=[];triangles=[];coords=[];rims=[];reports=[];size=135
    for sign in (-1,1):
        center,_,_=sphere(p[p[:,0]*sign>0]);lo=np.array([center[0]-2.2,center[2]-2.]);hi=lo+[4.4,4.]
        xs=lo[0]+(np.arange(size)+.5)/size*(hi[0]-lo[0]);zs=lo[1]+(np.arange(size)+.5)/size*(hi[1]-lo[1])
        body=checks.raster(skin,faces,np.zeros((len(faces),3,2)),np.ones((1,1)),basis,(lo,hi),size=size)
        source=checks.raster(p,t,uv,np.ones((1,1)),basis,(lo,hi),size=size,skin_depth=body['depth'])
        depth=np.where(np.isfinite(body['depth']),body['depth'],-100.)
        variants=rim_variants(xs,zs,depth);failures=[];chosen=None
        if not variants:raise ValueError('Aperture recovery found no unambiguous orbital recess')
        for variant in variants:
            rim=np.asarray(variant['bounds']);columns=sorted(set(rim[:,0]));lower=[];upper=[]
            for x in columns:
                values=rim[np.isclose(rim[:,0],x),2];lower.append(min(values)+.015);upper.append(max(values)-.015)
            bottom=np.interp(xs,columns,lower);top=np.interp(xs,columns,upper)
            opening=(zs[:,None]>=bottom)&(zs[:,None]<=top)&(xs>=columns[0])&(xs<=columns[-1])
            pupil=((xs[None,:]-center[0])**2+(zs[:,None]-center[2])**2)<.16**2
            original_inside=int((source['mask']&opening).sum())
            if original_inside<30 or pupil.sum()<3:continue
            for clearance in (.025,.075,.15,.25,.4,.6):
                try:
                    vp,ft,st=aperture_cap(center,xs,zs,opening,tree,eye_tree,p,t,uv,clearance)
                except ValueError as error:
                    failures.append(str(error));break
                vp=np.asarray(vp);ft=np.asarray(ft);st=np.asarray(st)
                after=checks.raster(vp,ft,st[ft],np.ones((1,1)),basis,(lo,hi),size=size,skin_depth=body['depth'])
                visible=after['mask'];inside=int((visible&opening).sum());spill=int((visible&~opening).sum())
                proof=dict(spill_fraction=spill/max(inside+spill,1),
                           pupil_visible_fraction=float((visible&pupil).sum()/pupil.sum()),
                           original_interior_coverage=inside/original_inside,inside_pixels=inside,
                           original_inside_pixels=original_inside,spill_pixels=spill)
                if proof['spill_fraction']<=.03 and proof['pupil_visible_fraction']>=.9 and proof['original_interior_coverage']>=.75:
                    chosen=(vp,ft,st,rim,dict(side=sign,status='measured_aperture',measurement=variant['name'],
                        rim_clearance_cm=clearance,uniform_globe_shift_used=False,triangles=len(ft),**proof));break
                failures.append(str(proof))
            if chosen:break
        if chosen is None:raise ValueError('Aperture recovery did not enclose the measured lid: '+str(failures[-3:]))
        vp,ft,st,rim,proof=chosen;triangles.extend(ft+len(points));points.extend(vp);coords.extend(st);rims.extend(rim.tolist());reports.append(proof)
    if len(triangles)>job['budgets']['eye']:raise ValueError('Aperture eye exceeds reserved budget')
    inverse=runtime_matrix(eye,{'sk_head':1.},native,cooked).inverted()
    mesh=bpy.data.meshes.new('source_textured_lid_caps');mesh.from_pydata(points,[],triangles);mesh.update();layer=mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        poly.use_smooth=True
        for li in poly.loop_indices:layer.data[li].uv=coords[mesh.loops[li].vertex_index]
    for material in eye.data.materials:mesh.materials.append(material)
    eye.data=mesh;eye.vertex_groups.clear();eye.vertex_groups.new(name='sk_head').add(list(range(len(points))),1.,'REPLACE')
    from_native_surface(mesh,inverse);job['eyelid_rim_points']=rims
    (Path(job['folder'])/'eye-enclosure.json').write_text(json.dumps(dict(eyes=reports,skin_geometry_changed=False,
        mode='measured_source_textured_aperture',source_eye_triangles=len(t),retained_triangles=len(triangles)),indent=2))
