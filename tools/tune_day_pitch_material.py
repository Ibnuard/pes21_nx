"""Local-only day shadow color override; retain accepted pitch bytes verbatim."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess

CONTENT = Path('PesMobile/Content/Assets/bg_lighting_AM1/Materials')

def parameters(node):
    if isinstance(node, dict):
        if node.get('StructType') == 'VectorParameterValue':
            fields = node['Value']
            info = next(v for v in fields if v['Name'] == 'ParameterInfo')
            name = next(v['Value'] for v in info['Value'] if v['Name'] == 'Name')
            value = next(v for v in fields if v['Name'] == 'ParameterValue')
            yield name, value['Value'][0]['Value']
        else:
            for value in node.values():
                yield from parameters(value)
    elif isinstance(node, list):
        for value in node:
            yield from parameters(value)

def patch_color(data, old, new):
    before = struct.pack('<4f', *old)
    after = struct.pack('<4f', *new)
    if data.count(before) != 1:
        raise ValueError('Expected one unique serialized shadowColor')
    offset = data.index(before)
    return data[:offset]+after+data[offset+16:], offset

def build(native, baseline, output, gui):
    output.mkdir(parents=True, exist_ok=False)
    stage = output/'stage'
    shutil.copytree(baseline, stage)
    if len(list(stage.rglob('*.*'))) != 27:
        raise ValueError('Expected accepted complete 27-member pitch baseline')
    records = []
    for name in ('MI_Pitch_L', 'MI_Pitch_R'):
        source = native/CONTENT/(name+'.uasset')
        document = output/(name+'.json')
        subprocess.run([str(gui), 'tojson', str(source), str(document), 'VER_UE4_22'], check=True)
        values = dict(parameters(json.loads(document.read_text(encoding='utf-8-sig'))))
        color = values['shadowColor']
        old = tuple(float(color[c]) for c in 'RGBA')
        if abs(old[0]-0.03125)>1e-8 or abs(old[1]-0.023696)>1e-8 or old[2:] != (0,1):
            raise ValueError('Unsupported native shadow color')
        weights = (0.2126,0.7152,0.0722)
        ratio = (0.60,1.0,0.29)
        level = sum(a*b for a,b in zip(old,weights))/sum(a*b for a,b in zip(ratio,weights))
        new = tuple(v*level for v in ratio)+(old[3],)
        target = stage/CONTENT/source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        raw = source.with_suffix('.uexp').read_bytes()
        patched, offset = patch_color(raw, old, new)
        target.with_suffix('.uexp').write_bytes(patched)
        check = output/(name+'-verify.json')
        subprocess.run([str(gui), 'tojson', str(target), str(check), 'VER_UE4_22'], check=True)
        decoded = dict(parameters(json.loads(check.read_text(encoding='utf-8-sig'))))['shadowColor']
        for c,v in zip('RGBA',new):
            if abs(float(decoded[c])-v)>1e-8:
                raise ValueError('Serialized color verification failed')
        records.append(dict(material=name, old=old, new=new, offset=offset))
    for original in baseline.rglob('*'):
        if original.is_file() and original.read_bytes() != (stage/original.relative_to(baseline)).read_bytes():
            raise ValueError('Accepted baseline modified')
    assert len(list(stage.rglob('*.*'))) == 31
    (output/'report.json').write_text(json.dumps(records,indent=2))
    print('Verified 27 baseline files unchanged; added 4 day material files')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('native','baseline','output','gui'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    build(args.native.resolve(), args.baseline.resolve(), args.output.resolve(), args.gui.resolve())
