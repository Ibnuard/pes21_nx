"""Measure a cheap roof proxy from a local shell; run inside Blender.

Uses elevated, mostly horizontal surfaces. The JSON and mask require visual
review: this is a fitted lighting approximation, not native shadow-map recovery.
"""
import argparse,json,sys,math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--blend',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--min-height',type=float,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
tree=BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())
xs=np.arange(-175,176,1.);ys=np.arange(-145,146,1.)
heights=np.zeros((len(ys),len(xs)),dtype=float)
for iy,y in enumerate(ys):
    for ix,x in enumerate(xs):
        point,normal,index,dist=tree.ray_cast(Vector((x,-y,110)),Vector((0,0,-1)),125)
        if point is not None and point.z>=a.min_height and abs(normal.z)>.65:
            heights[iy,ix]=point.z
sides=[]
for axis,sign in ((0,-1),(0,1),(1,-1),(1,1)):
    segments=[]
    for band in (-20,-10,0,10,20):
        line=heights[np.argmin(abs(ys-band)),:] if axis==0 else heights[:,np.argmin(abs(xs-band))]
        coord=xs if axis==0 else ys
        candidates=[(float(c)*sign,float(h)) for c,h in zip(coord,line) if c*sign>(52.5 if axis==0 else 34) and h>0]
        candidates.sort()
        # Ignore isolated thin poles, fences and fixtures, requiring a broad panel.
        groups=[]
        for c,h in candidates:
            if not groups or c-groups[-1][-1][0]>3:groups.append([])
            groups[-1].append((c,h))
        groups=[g for g in groups if g[-1][0]-g[0][0]>=8]
        if groups:
            g=groups[0];segments.append([g[0][0],g[-1][0],float(np.median([v[1] for v in g]))])
    sides.append(dict(axis=axis,sign=sign,samples=segments,enabled=len(segments)>=3,
                      fit=np.median(segments,axis=0).tolist() if segments else None))
for i,s in enumerate(sides):
    if not s['enabled']:
        s['fit']=[55 if i<2 else 39,110 if i<2 else 95,a.min_height]
ix=(sides[0]['fit'][0]+sides[1]['fit'][0])*.5
iy=(sides[2]['fit'][0]+sides[3]['fit'][0])*.5
ox=(sides[0]['fit'][1]+sides[1]['fit'][1])*.5
oy=(sides[2]['fit'][1]+sides[3]['fit'][1])*.5
cx=(sides[1]['fit'][0]-sides[0]['fit'][0])*.5
cy=(sides[3]['fit'][0]-sides[2]['fit'][0])*.5
height=float(np.median([s['fit'][2] for s in sides if s['enabled']]))
if not math.isfinite(height) or not 15<height<80:raise ValueError('No bounded roof fit')
report=dict(min_height=a.min_height,sides=sides,
    inner=[ix*100,iy*100,150.,height*100],outer=[ox*100,oy*100,250.,0.],
    center=[cx*100,cy*100,0.,0.],enabled=[float(s['enabled']) for s in sides],
    scope='axis-sampled elevated surfaces; analytic roof approximation requiring preview review')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2))
np.save(a.output.with_suffix('.npy'),heights)
print('PESNX_ROOF_AUDIT_OK',json.dumps(report))
