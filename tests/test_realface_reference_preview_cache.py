"""Reference regrouping must preserve identity, stage and rendering recipe."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_batch_inventory import read,write
from realface_pipeline import sha
import realface_reference_preview_cache as cache


def fixture(tmp_path, stage='source'):
    root=tmp_path/'comparisons'
    output=root/'old-group'/stage
    output.mkdir(parents=True)
    rows=[dict(base_id=1,native_player_id=11,fingerprint='owner',cache_key='prepared-key')]
    catalogue={1:dict(input_hashes={'own-source':'source-hash'})}
    owners=cache.owners(stage,rows,catalogue)
    header=cache.header(dict(work_dir=str(tmp_path)),stage,'renderer','preview-tool')
    image=output/'1-front.png';image.write_bytes(b'reference-image')
    write(image.with_suffix('.json'),dict(prepared_key=owners[1]['prepared_key'],cooked_key=None,
        renderer_sha256='renderer',view='front',image_sha256=sha(image)))
    write(output/'PROVENANCE.json',dict(stage=stage,players=[dict(base_id=1)]))
    cache.seal_references(output,header,owners)
    return root,output,header,owners


def test_exact_reference_can_be_reused_after_regrouping_without_acceptance(tmp_path):
    root,output,header,owners=fixture(tmp_path)
    found=cache.index_references(root,header,owners)
    new=root/'different-group'/'source'
    cache.seed_references(new,owners,found)
    assert (new/'1-front.png').read_bytes()==(output/'1-front.png').read_bytes()
    assert read(new/'1-front.json')==read(output/'1-front.json')
    receipt=read(output/'REFERENCE-COMPLETE.json')
    assert not receipt['valid_for_cooked_acceptance'] and not receipt['inspected_automatically']
    assert not (tmp_path/'VISUAL-REVIEW.json').exists()


@pytest.mark.parametrize('changed',['stage','config_key','renderer_sha256','preview_tool_sha256',
                                    'prepared_key','fingerprint','native_player_id'])
def test_changed_stage_owner_or_recipe_is_not_reused(tmp_path,changed):
    root,output,header,owners=fixture(tmp_path)
    if changed in header: header[changed]='different'
    else: owners[1][changed]='different'
    assert cache.index_references(root,header,owners)=={}


@pytest.mark.parametrize('changed',['image','metadata','unsealed'])
def test_changed_or_unsealed_reference_is_not_reused(tmp_path,changed):
    root,output,header,owners=fixture(tmp_path)
    if changed=='image': (output/'1-front.png').write_bytes(b'changed-image')
    elif changed=='metadata':
        proof=read(output/'1-front.json');proof['cooked_key']='a-cooked-asset'
        write(output/'1-front.json',proof)
    else: (output/'REFERENCE-COMPLETE.json').unlink()
    assert cache.index_references(root,header,owners)=={}


def test_mutation_after_indexing_is_rejected_before_copying(tmp_path):
    root,output,header,owners=fixture(tmp_path)
    found=cache.index_references(root,header,owners)
    (output/'1-front.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='changed during reuse'):
        cache.seed_references(root/'new-group'/'source',owners,found)


def test_cooked_stage_and_mismatched_manifest_cannot_be_sealed(tmp_path):
    with pytest.raises(ValueError,match='source/prepared'):
        cache.owners('cooked',[],{})
    root,output,header,owners=fixture(tmp_path)
    write(output/'PROVENANCE.json',dict(stage='prepared',players=[dict(base_id=1)]))
    with pytest.raises(ValueError,match='stage/owners'):
        cache.seal_references(output,header,owners)
