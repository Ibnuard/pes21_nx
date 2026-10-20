from pathlib import Path
import json
import sys
import subprocess

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_material_slots import invisible_hair_aliases


@pytest.fixture
def slot(tmp_path):
    profile = dict(opaque_eye_atlas=True,hair_materials=['lite_hair'],hair_skin_materials=[],
                   hair_fbx=str(tmp_path/'hair.fbx'),hair_texture=str(tmp_path/'hair-shell.png'))
    proof = dict(policy='proven_alpha_hidden_or_rigid_microscopic_source_slot_v1',unproven=0,
                 replacement_triangles=1,source_skin_changed=False,visible_source_removed=False)
    (tmp_path/'invisible-source-slot-proof.json').write_text(json.dumps(proof),encoding='utf-8')
    return profile,proof,tmp_path/'invisible-source-slot-proof.json'


def test_accepts_only_exact_ue_and_blender_suffix_for_proven_slot(slot):
    profile,_,_ = slot
    assert invisible_hair_aliases(profile)=={'lite_hair_001':'lite_hair','lite_hair.001':'lite_hair'}
    assert 'lite_hair_002' not in invisible_hair_aliases(profile)


@pytest.mark.parametrize('change',[
    dict(opaque_eye_atlas=False),dict(hair_materials=['other_hair']),
    dict(hair_skin_materials=['skin']),dict(hair_materials=['lite_hair','other_hair'])])
def test_does_not_guess_roles_for_other_profiles(slot,change):
    profile,_,_ = slot
    assert invisible_hair_aliases(dict(profile,**change))=={}


def test_missing_or_different_owner_proof_does_not_enable_alias(slot,tmp_path):
    profile,_,path = slot
    assert invisible_hair_aliases(dict(profile,hair_texture=str(tmp_path/'other'/'hair.png')))=={}
    path.unlink()
    assert invisible_hair_aliases(profile)=={}


@pytest.mark.parametrize('change',[
    dict(policy='unchecked'),dict(unproven=1),dict(replacement_triangles=2),
    dict(source_skin_changed=True),dict(visible_source_removed=True)])
def test_rejects_incomplete_or_changed_slot_proof(slot,change):
    profile,proof,path = slot
    path.write_text(json.dumps(dict(proof,**change)),encoding='utf-8')
    with pytest.raises(ValueError,match='slot proof'):
        invisible_hair_aliases(profile)


def test_editor_python_can_read_real_profile_proof(slot):
    editor_python=Path('D:/UE_4.22/Engine/Binaries/ThirdParty/Python/Win64/python.exe')
    if not editor_python.is_file():
        pytest.skip('Optional local UE 4.22 Python runtime is unavailable')
    profile,_,proof_path=slot
    path=proof_path.with_name('profile.json')
    path.write_text(json.dumps(profile),encoding='utf-8')
    script=('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from realface_material_slots import invisible_hair_aliases;'
            'p=json.load(open(sys.argv[2]));'
            'assert invisible_hair_aliases(p)["lite_hair_001"]=="lite_hair"')
    subprocess.run([str(editor_python),'-B','-c',script,str(Path(__file__).resolve().parents[1]/'tools'),str(path)],check=True)


def test_preview_adapter_recognizes_the_same_proof_without_mutating_profile(slot):
    from realface_league_preview import preview_profile
    profile,_,_=slot
    result=preview_profile(profile)
    assert set(result['hair_materials'])=={'lite_hair','lite_hair.001','lite_hair_001'}
    assert profile['hair_materials']==['lite_hair']
    assert preview_profile(dict(profile,hair_materials=['visible_hair'])) is None
