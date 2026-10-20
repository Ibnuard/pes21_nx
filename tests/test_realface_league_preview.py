import json
from pathlib import Path
import sys

from PIL import Image,ImageFont
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_league_preview as preview
import realface_lite
from realface_batch_inventory import read,write
from realface_pipeline import sha


def fixture(tmp_path,monkeypatch):
    row=dict(base_id=12,native_player_id=44,name='Player',status='prepared',
        folder=str(tmp_path/'prepared'),cache_key='new',budgets={})
    write(tmp_path/'prepare-report.json',[row])
    write(tmp_path/'prepared/ue-profile.json',{})
    output=tmp_path/'prepared-review';output.mkdir()
    Image.new('RGB',(16,16),'red').save(output/'12-front.png')
    write(output/'12-front.json',{'prepared_key':'old'})
    monkeypatch.setattr(preview,'valid_prepared_cache',lambda *args:True)
    font=ImageFont.load_default();monkeypatch.setattr(preview.ImageFont,'truetype',lambda *a,**k:font)
    return dict(work_dir=str(tmp_path),blender='fake',native_rig='n',cooked_rig='c'),output


def test_failed_render_cannot_label_old_image_as_new_recipe(tmp_path,monkeypatch):
    config,output=fixture(tmp_path,monkeypatch)
    def fail(*args):raise RuntimeError('render interrupted')
    monkeypatch.setattr(preview,'command',fail)
    with pytest.raises(RuntimeError,match='interrupted'):preview.preview(config,stage='prepared')
    assert read(output/'12-front.json')=={'prepared_key':'old'}
    assert not (output/'PROVENANCE.json').exists()


def test_multiview_previews_are_hashed_only_after_success(tmp_path,monkeypatch):
    config,output=fixture(tmp_path,monkeypatch)
    def render(*args):
        for target in read(output/'targets.json'):
            Image.new('RGB',(16,16),'blue').save(target['output'])
    monkeypatch.setattr(preview,'command',render)
    preview.preview(config,stage='prepared',views=('front','left','right'))
    for view in ('front','left','right'):
        proof=read(output/(str(12)+'-'+view+'.json'))
        assert proof['prepared_key']=='new' and proof['view']==view
        assert proof['image_sha256']==sha(output/(str(12)+'-'+view+'.png'))
    provenance=read(output/'PROVENANCE.json')
    assert provenance['mesh']=='prepared_fbx' and not provenance['hardware_capture']
    monkeypatch.setattr(preview,'command',lambda *args:pytest.fail('Valid images should be cached'))
    preview.preview(config,stage='prepared',views=('front','left','right'))


def test_dense_source_reference_is_hashed_and_cannot_be_cooked_acceptance(tmp_path,monkeypatch):
    source=tmp_path/'original';source.mkdir()
    profile=source/'ue-profile.json';write(profile,dict(base_id=10,native_player_id=90,fingerprint='owner'))
    fbx=source/'face.fbx';fbx.write_bytes(b'authored source fixture')
    owner=dict(base_id=10,native_player_id=90,fingerprint='owner',name='Player',profile=str(profile),
               input_hashes={str(p):sha(p) for p in (profile,fbx)})
    monkeypatch.setattr(realface_lite,'sources',lambda config:[owner])
    font=ImageFont.load_default();monkeypatch.setattr(preview.ImageFont,'truetype',lambda *a,**k:font)
    seen=[]
    def renderer(targets,log):
        targets=read(targets);seen.extend(targets)
        for target in targets:Image.new('RGB',(32,32),'gray').save(target['output'])
    config=dict(work_dir=str(tmp_path),native_rig='native',cooked_rig='cooked')
    output=tmp_path/'review'
    preview.preview(config,stage='source',selected={10},output=output,render_worker=renderer)
    proof=read(output/'10-front.json');provenance=read(output/'PROVENANCE.json')
    assert seen[0]['recipe']['ue']['fingerprint']=='owner'
    assert proof['cooked_key'] is None and proof['image_sha256']==sha(output/'10-front.png')
    assert provenance['mesh']=='source_fbx' and not provenance['hardware_capture']
    fbx.write_bytes(b'changed source')
    with pytest.raises(ValueError,match='source preview inputs changed'):
        preview.preview(config,stage='source',selected={10},output=output,render_worker=renderer)
    assert len(seen)==1
