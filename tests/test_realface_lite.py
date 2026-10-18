"""Identity and offline reducer contracts; no proprietary fixtures required."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from realface_lite import sources, package


def fixture(tmp_path):
    row=dict(base_id=7,native_player_id=100,fingerprint='player-seven')
    documents=dict(source_profiles=[row],identity_state=dict(identities={'7':dict(
        row,status='active',name='Synthetic player')}),source_verification=dict(
        players=[dict(row,status='candidate_pending_device')]))
    config=dict(work_dir=str(tmp_path))
    for name,value in documents.items():
        path=tmp_path/(name+'.json');path.write_text(json.dumps(value))
        config[name]=str(path)
    return config,row


def test_reused_native_slot_cannot_carry_old_face(tmp_path):
    config,row=fixture(tmp_path)
    assert sources(config)[0]['name']=='Synthetic player'
    path=Path(config['identity_state']);state=json.loads(path.read_text())
    state['identities']['7']['fingerprint']='new-person'
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError,match='fingerprint'):sources(config)


@pytest.mark.parametrize('change',['duplicate','missing','wrong_native','unaccepted'])
def test_source_coverage_is_exact(tmp_path,change):
    config,row=fixture(tmp_path)
    rows=[row]
    if change=='duplicate':rows.append(dict(row))
    if change=='missing':rows=[]
    if change=='wrong_native':rows[0]['native_player_id']=101
    if change=='unaccepted':rows[0]['base_id']=8
    Path(config['source_profiles']).write_text(json.dumps(rows))
    with pytest.raises(ValueError):sources(config)


def test_packaging_refuses_held_or_incomplete_batch_before_any_asset_write(tmp_path):
    config,row=fixture(tmp_path)
    for rows in ([],[dict(row,status='held_cook_validation')]):
        (tmp_path/'verify-report.json').write_text(json.dumps(rows))
        with pytest.raises(ValueError,match='All accepted players'):package(config)
        assert not (tmp_path/'package-stage').exists()


def test_packaging_rechecks_verified_row_identity_and_uniqueness(tmp_path):
    config,row=fixture(tmp_path)
    verified=dict(row,status='validated')
    for rows in ([verified,verified], [dict(verified,native_player_id=101)],
                 [dict(verified,fingerprint='different-person')]):
        (tmp_path/'verify-report.json').write_text(json.dumps(rows))
        with pytest.raises(ValueError):package(config)
        assert not (tmp_path/'package-stage').exists()


def test_distinct_identities_cannot_write_the_same_native_mesh_paths(tmp_path):
    config, first = fixture(tmp_path)
    second = dict(base_id=8, native_player_id=100, fingerprint='player-eight')
    Path(config['source_profiles']).write_text(json.dumps([first, second]))
    Path(config['source_verification']).write_text(json.dumps(dict(players=[
        dict(row, status='candidate_pending_device') for row in (first, second)])))
    Path(config['identity_state']).write_text(json.dumps(dict(identities={
        str(row['base_id']): dict(row, status='active', name='Synthetic player')
        for row in (first, second)})))
    (tmp_path/'verify-report.json').write_text(json.dumps([
        dict(row, status='validated') for row in (first, second)]))
    with pytest.raises(ValueError, match='Multiple owners of the native slot'):
        package(config)
    assert not (tmp_path/'package-stage').exists()


def test_reducer_handles_target_larger_than_welded_source(tmp_path):
    module=ROOT/'local-inputs/meshoptimizer-tools-v1/node_modules/meshoptimizer/meshopt_simplifier.js'
    node=shutil.which('node')
    if not module.is_file() or not node:
        pytest.skip('Optional local meshoptimizer 1.1.1 and Node runtime unavailable')
    request=dict(positions=[0,0,0,1,0,0,0,1,0],uv=[0,0,1,0,0,1],
        indices=[0,1,2],locks=[1,1,1],target=500,error=.1,uvWeight=.3,
        flags=['ErrorAbsolute'])
    source=tmp_path/'source.json';output=tmp_path/'out.json'
    source.write_text(json.dumps(request))
    subprocess.run([node,str(ROOT/'tools/meshopt_reduce.mjs'),str(module),str(source),str(output)],check=True)
    result=json.loads(output.read_text())
    assert result['indices']==[0,1,2]
    assert result['verticesMoved'] is False


def test_microscopic_markers_do_not_hide_long_thin_hair_cards(tmp_path):
    blender=ROOT/'local-debug/lamine-yamal-face-canary/third-party/blender-4.5.13/blender-4.5.13-windows-x64/blender.exe'
    if not blender.is_file():pytest.skip('Optional local Blender runtime unavailable')
    script=tmp_path/'surface.py'
    script.write_text('''import sys
sys.path.insert(0, TOOLS)
import bpy
from mathutils import Vector
import blender_realface_lite as lite
mesh=bpy.data.meshes.new('Synthetic hair')
mesh.from_pydata([(0,0,160),(.01,0,160),(0,.01,160),
                 (0,0,180),(5,0,180),(5,.0001,180)],[],[(0,1,2),(3,4,5)])
obj=bpy.data.objects.new('Synthetic hair',mesh)
lite.points=lambda obj,native,cooked:[v.co.copy() for v in obj.data.vertices]
points,faces=lite.surface(obj,{}, {})
assert faces==[(3,4,5)],faces
assert lite.quality(points,faces,obj,{}, {})['max_cm']<.001
for v in obj.data.vertices:v.co.z+=5
assert lite.quality(points,faces,obj,{}, {})['max_cm']>4.9
'''.replace('TOOLS',repr(str(ROOT/'tools'))))
    result=subprocess.run([str(blender),'--background','--threads','1','--python-exit-code','1',
                    '--python',str(script)],capture_output=True)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
