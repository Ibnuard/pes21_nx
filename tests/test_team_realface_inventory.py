"""Identity matching and rig rejection use synthetic data, never game fixtures."""
import base64
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inventory_team_realfaces import select_source
from audit_realface_rig import audit_rig
from realface_material_policy import classify


def test_reused_id_is_not_source_identity():
    target=dict(base_id=7,name='Correct Player')
    native=SimpleNamespace(nationality_code=10)
    candidates={7:SimpleNamespace(player_id=7,name='Other Player',nationality_code=10),
                100:SimpleNamespace(player_id=100,name='Correct Player',nationality_code=10)}
    source,status=select_source(target,native,candidates)
    assert source.player_id==100 and status=='verified_name_country'


def test_ambiguous_name_country_is_held_for_review():
    target=dict(name='Correct Player');native=SimpleNamespace(nationality_code=10)
    candidate=SimpleNamespace(name='Correct Player',nationality_code=10)
    assert select_source(target,native,{1:candidate,2:candidate})==(None,'ambiguous_identity')
    assert select_source(target,native,{1:SimpleNamespace(name='Correct Player',nationality_code=20)})==(None,'missing_identity')


def rig_fixture():
    reference=[dict(name='root_main',parent=-1,trs=[0,0,0,1,0,0,0,1,1,1]),
               dict(name='sk_head',parent=0,trs=[0,0,0,1,0,0,170,1,1,1])]
    raw=(b'opaque prefix'+struct.pack('<I',2)+struct.pack('<iii',0,0,-1)+
         struct.pack('<iii',1,0,0)+struct.pack('<I',2)+
         b''.join(struct.pack('<10f',*b['trs']) for b in reference)+b'opaque suffix')
    document=dict(NameMap=['root_main','sk_head'],Exports=[dict(Extras=base64.b64encode(raw).decode())],Imports=[dict(ObjectName='test_body_Skeleton')])
    return document,reference,raw


def test_cooked_rig_accepts_equivalent_quaternion_and_exposes_actual_pose():
    doc,reference,raw=rig_fixture();reference[1]['trs'][:4]=[0,0,0,-1]
    result=audit_rig(doc,reference,True)
    assert result['bones']==2 and result['max_component_drift']==0
    assert result['embedded_rig'][1]['trs'][6]==170


def test_duplicate_or_changed_embedded_rig_is_rejected():
    doc,reference,raw=rig_fixture()
    doc['Exports'][0]['Extras']=base64.b64encode(raw+raw).decode()
    with pytest.raises(ValueError,match='differs'):audit_rig(doc,reference)
    doc,reference,_=rig_fixture();reference[1]['trs'][6]=169
    with pytest.raises(ValueError,match='differs'):audit_rig(doc,reference)
    reference[1]['parent']=-1
    with pytest.raises(ValueError,match='differs'):audit_rig(doc,reference)


def test_material_names_cannot_swap_skin_hair_and_wet_overlays():
    def material(technique,base='face_bsm_alp.dds'):
        return dict(name='fox_skin_mat',extras=dict(fmdlTechnique=technique,
                    fmdlTextures=[dict(role='Base_Tex_SRGB',filename=base)]))
    assert classify(material('pes3DDC_Wet'))['role']=='effect'
    assert classify(material('pes3DDF_Hair2_NrmUV','hair_parts_bsm_alp.dds'))['role']=='hair'
    assert classify(material('pes3DDF_Skin_Face'))['role']=='skin'
    dual=material('pes3DDF_Hair2_NrmUV','hair_parts_bsm_alp.dds')
    dual['extras']['fmdlTextures'].append(dict(role='Base_Tex_2_SRGB',filename='cap_parts_bsm_alp.dds'))
    assert classify(dual)['requires_texture_bake']
