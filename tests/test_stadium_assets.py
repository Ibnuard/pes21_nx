from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as O
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_assets import asset_key,material_key,discover
from stadium_geometry import trim_shell,overlaps_pitch


def test_standalone_inventory_requires_one_shell_and_owned_audience(tmp_path):
    folder=tmp_path/'Example Stadium'/'Asset/model/bg/st056'
    (folder/'#Win').mkdir(parents=True)
    (folder/'#Win/st056.fpk').write_bytes(b'fixture')
    row=discover(tmp_path)[0]
    assert row['source_id']=='st056' and row['key']=='ExampleStadium'
    assert row['status']=='missing_audience'
    (folder/'audi/#Win').mkdir(parents=True)
    (folder/'audi/#Win/audiarea_st056.fpk').write_bytes(b'fixture')
    assert discover(tmp_path)[0]['status']=='available'
    for value in ('../Anfield','foo/bar','A.B','A\\B','', '7Venue'):
        with pytest.raises(ValueError):asset_key(value)


def test_native_pitch_clearance_catches_large_crossing_faces_without_losing_roof():
    material=O(name='owned')
    def face(points):return O(vertices=[O(position=O(x=x,y=y,z=z)) for x,y,z in points])
    pitch=face([(-70,0,-45),(70,0,-45),(0,0,70)])
    roof=face([(-70,30,-45),(70,30,-45),(0,30,70)])
    stand=face([(60,0,40),(60,20,60),(90,0,40)])
    city=face([(500,0,400),(501,0,400),(500,0,401)])
    faces=[pitch,roof,stand,city]
    mesh=O(faces=faces,vertices=[v for f in faces for v in f.vertices],materialInstance=material)
    model=O(meshes=[mesh],materialInstances=[material])
    removed=trim_shell(model)
    assert removed['native_pitch_overlap']==1 and removed['distant_exterior']==1
    assert roof in mesh.faces and stand in mesh.faces
    assert removed['apron_fragments_retained']>0
    for triangle in mesh.faces:
        if triangle is roof or triangle is stand:continue
        # Outside pieces may touch the boundary but never cover pitch interior.
        centre=[sum(getattr(v.position,k) for v in triangle.vertices)/3 for k in 'xz']
        assert abs(centre[0])>=53.5 or abs(centre[1])>=35
    assert not overlaps_pitch([(60,0,40),(90,0,40),(60,0,70)])


def test_unreal_material_names_are_stable_and_do_not_alias():
    import re
    values=['M_sedili panca','M_sedili-panca','M_sedili_panca','M_'+100*'a']
    names=[material_key(v) for v in values]
    assert len(set(names))==4
    for value,name in zip(values,names):
        assert re.fullmatch('[A-Za-z0-9_]{1,60}',name)
        assert material_key(value)==name and material_key(name)==name


def test_roof_profiles_match_catalog_and_reviewed_manifest():
    import json,re
    root=Path(__file__).resolve().parents[1]
    rows=json.loads((root/'data/stadiums/fl26_addons_v25.json').read_text())['stadiums']
    header=(root/'source/stadium_roof_profiles.h').read_text()
    catalog=(root/'source/stadium_catalog.h').read_text()
    assert len(rows)==10
    assert 'ANFIELD TEST' not in catalog and 'ANFIELD STADIUM' in catalog
    assert re.findall(r'NX_SHELL\("([^\"]+)"',catalog)[1:]==[r['key'] for r in rows]+['OldTrafford','CampNou']
    for row in rows:
        line=next(s for s in header.splitlines() if '/* '+row['key']+' */' in s)
        values=[float(v) for v in line.split('{')[1].split('}')[0].split(',')]
        assert values==row['roof_cm']
        assert 1500<values[3]<8000 and 0<=values[2]<=min(values[:2])
        assert values[4]>values[0] and values[5]>values[1]
        assert min(row['roof_fit_iou'])>=.8


def test_selected_stadiums_keep_stable_ids_and_old_trafford_roof():
    import json
    root=Path(__file__).resolve().parents[1]
    rows=json.loads((root/'data/stadiums/fl26_selected_v27.json').read_text())['stadiums']
    assert [r['key'] for r in rows]==['EtihadStadium','SanSiro','SantiagoBernabeu','SignalIdunaPark','StamfordBridge','OldTrafford']
    header=(root/'source/stadium_roof_profiles.h').read_text()
    for row in rows:
        line=next(s for s in header.splitlines() if '/* '+row['key']+' */' in s)
        values=[float(v) for v in line.split('{')[1].split('}')[0].split(',')]
        assert values==pytest.approx(row['roof_cm'],abs=.005)
        assert min(row['roof_fit_iou'])>=.8


def test_v30_manifest_retires_heavy_roofs_and_adds_owned_camp_nou():
    import json
    root=Path(__file__).resolve().parents[1]
    rows=json.loads((root/'data/stadiums/fl26_selected_v30.json').read_text())['stadiums']
    assert [r['key'] for r in rows]==['EtihadStadium','SignalIdunaPark','StamfordBridge','OldTrafford','CampNou']
    camp=rows[-1]
    assert camp['source_id']=='st002' and camp['triangle_budget']==30000
    assert camp['roof_cm'][12:]==[0,0,0,1] and min(camp['roof_fit_iou'])>=.8
    header=(root/'source/stadium_roof_profiles.h').read_text()
    line=next(s for s in header.splitlines() if '/* CampNou */' in s)
    values=[float(v) for v in line.split('{')[1].split('}')[0].split(',')]
    assert values==pytest.approx(camp['roof_cm'],abs=.005)
