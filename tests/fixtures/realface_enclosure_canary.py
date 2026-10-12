"""Blender: buried skin must stay enclosed in posed geometry, not just at rest."""
from pathlib import Path
import sys
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from blender_fit_realface import body_enclosure_auditor

names=['sk_chest','sk_neck','sk_head','sk_shoulder_l','sk_shoulder_r']
parents=[-1,0,1,0,0]
rows=[dict(name=n,parent=p) for n,p in zip(names,parents)]
rig={n:Matrix.Translation((0,0,170 if n in ('sk_neck','sk_head') else 140)) for n in names}
vertices=[(-5,-5,135),(5,-5,135),(5,5,135),(-5,5,135),
          (-5,-5,160),(5,-5,160),(5,5,160),(-5,5,160)]
quads=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
faces=[t for a,b,c,d in quads for t in ((a,b,c),(a,c,d))]
body=dict(vertices=vertices,faces=faces,weights=[{'sk_chest':1.}]*8)
enclosed=body_enclosure_auditor(rows,rig,rig,body)
assert enclosed(Vector((0,0,145)),{'sk_chest':1.})
assert not enclosed(Vector((6,0,145)),{'sk_chest':1.})
assert not enclosed(Vector((4.98,0,145)),{'sk_chest':1.})
# This point starts inside but escapes when the neck tilts around z=170.
assert not enclosed(Vector((0,0,145)),{'sk_head':1.})
opened=dict(body,faces=[t for t in faces if not all(vertices[i][1]==5 for i in t)])
assert not body_enclosure_auditor(rows,rig,rig,opened)(Vector((0,0,145)),{'sk_chest':1.})
print('Enclosure guard: contained body accepted; exterior, clearance, posed escape and open shell rejected')
