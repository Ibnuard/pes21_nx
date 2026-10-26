"""Author one bounded podium-local golden spark field, without game assets.

Four fountains behind the canonical podium share one mesh/material/primitive.
128 sparks use two crossing quads each (1,024 vertices, 512 triangles). UV0's
integer U selects a deterministic ballistic trajectory; no particle actors,
textures, collision, lighting or per-frame vertex uploads are needed.
"""
import argparse
import hashlib
import json
from pathlib import Path

SPARKS = 128
EMITTERS_CM = ((-425., 360., 55.), (-145., 360., 55.),
               (145., 360., 55.), (425., 360., 55.))
PERIOD = 2.0
MAX_HEIGHT_CM = 420.


def field():
    vertices, uvs, faces = [], [], []
    for particle in range(SPARKS):
        x, y, z = EMITTERS_CM[particle % len(EMITTERS_CM)]
        for plane in range(2):
            start = len(vertices)
            for side, up, u, v in ((-1,-1,.1,.1),(1,-1,.9,.1),
                                    (1,1,.9,.9),(-1,1,.1,.9)):
                vertices.append((x + (side*1.5 if not plane else 0.),
                                 y + (side*1.5 if plane else 0.), z + up*7.))
                uvs.append((particle+u,v))
            faces.extend(((start,start+1,start+2),(start,start+2,start+3)))
    return vertices, uvs, faces


def trajectory(particle, clock):
    """CPU reference for the authored shader, for independent bounds checks."""
    phase = (particle+.5)/SPARKS
    t = (clock/PERIOD+phase) % 1.
    seed = (particle*.61803398875) % 1.
    return ((seed-.5)*160.*t, (((particle*.38196601125) % 1.)-.5)*120.*t,
            4.*MAX_HEIGHT_CM*t*(1.-t))


def write(output):
    output = Path(output)
    vertices, uvs, faces = field()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='\n', encoding='ascii') as stream:
        stream.write('# FootballNX authored podium sparks, centimetres, Z-up\no PodiumSparks\n')
        for row in vertices: stream.write('v %.7f %.7f %.7f\n' % row)
        for row in uvs: stream.write('vt %.7f %.7f\n' % row)
        for face in faces:
            stream.write('f '+' '.join('%d/%d' % (i+1,i+1) for i in face)+'\n')
    return {'mesh':str(output), 'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'sparks':SPARKS, 'vertices':len(vertices), 'triangles':len(faces),
            'emitters_local_cm':EMITTERS_CM, 'period_seconds':PERIOD,
            'ballistic_height_cm':MAX_HEIGHT_CM, 'faithful_pc_fx_port':False,
            'authored_approximation':True, 'device_tested':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    print(json.dumps(write(p.parse_args().output),indent=2))
