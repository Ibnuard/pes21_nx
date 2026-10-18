import json
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_league_preview as preview


def fixture(tmp_path,monkeypatch):
    row=dict(base_id=12,native_player_id=44,name='Player',status='prepared',
        folder=str(tmp_path/'prepared'),cache_key='new',budgets={})
    (tmp_path/'prepare-report.json').write_text(json.dumps([row]))
    output=tmp_path/'prepared-review';output.mkdir()
    Image.new('RGB',(16,16),'red').save(output/'12-front.png')
    (output/'12-front.json').write_text(json.dumps({'prepared_key':'old'}))
    monkeypatch.setattr(preview,'valid_prepared_cache',lambda *args:True)
    return dict(work_dir=str(tmp_path),blender='fake',native_rig='n',cooked_rig='c'),output


def test_failed_render_cannot_label_old_image_as_new_recipe(tmp_path,monkeypatch):
    config,output=fixture(tmp_path,monkeypatch)
    def fail(*args):raise RuntimeError('render interrupted')
    monkeypatch.setattr(preview,'command',fail)
    with pytest.raises(RuntimeError,match='interrupted'):preview.preview(config,stage='prepared')
    assert json.loads((output/'12-front.json').read_text())=={'prepared_key':'old'}
    assert not (output/'PROVENANCE.json').exists()


def test_multiview_previews_are_hashed_only_after_success(tmp_path,monkeypatch):
    config,output=fixture(tmp_path,monkeypatch)
    def render(*args):
        for target in json.loads((output/'targets.json').read_text()):
            Image.new('RGB',(16,16),'blue').save(target['output'])
    monkeypatch.setattr(preview,'command',render)
    preview.preview(config,stage='prepared',views=('front','left','right'))
    for view in ('front','left','right'):
        proof=json.loads((output/('12-'+view+'.json')).read_text())
        assert proof['prepared_key']=='new' and proof['view']==view
        assert proof['image_sha256']==preview.sha(output/('12-'+view+'.png'))
    provenance=json.loads((output/'PROVENANCE.json').read_text())
    assert provenance['mesh']=='prepared_fbx' and not provenance['hardware_capture']
    monkeypatch.setattr(preview,'command',lambda *args:pytest.fail('Valid images should be cached'))
    preview.preview(config,stage='prepared',views=('front','left','right'))
