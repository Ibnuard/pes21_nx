"""Texture policy tests use generated colors/UVs, without game data."""
from pathlib import Path
import sys
from types import SimpleNamespace as Bag

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_material_atlas import build_atlas


def mesh(name, uv, tint=(1, 1, 1, 1), technique='pes3DDF_Hair2_NrmUV'):
    material = Bag(name=name, technique=technique,
                   textures=[('Base_Tex_SRGB', Bag(filename=name + '.dds')),
                             ('Base_Tex_2_SRGB', Bag(filename='omitted.dds'))],
                   parameters=[('HairColor', tint)])
    vertices = [Bag(uv=[Bag(u=u, v=v)], position=(1, 2, 3), boneMapping={'head': 1}) for u, v in uv]
    return Bag(materialInstance=material, vertices=vertices)


def test_atlas_keeps_wrap_seams_continuous_and_records_shader_approximation(tmp_path):
    source = Image.new('RGBA', (256, 256), (230, 0, 0, 77))
    source.paste((0, 0, 230, 77), (128, 0, 256, 256))
    source.save(tmp_path / 'hair.png')
    m = mesh('hair', [(.9, .5), (1.1, .5), (.5, .5)])
    output, audit = build_atlas(dict(face=Bag(meshes=[m])), tmp_path, tmp_path / 'atlas.png')
    assert m.vertices[1].uv[0].u - m.vertices[0].uv[0].u == pytest.approx(.1)
    with Image.open(output) as atlas:
        assert atlas.size == (512, 256)
        assert atlas.getpixel((int(m.vertices[0].uv[0].u * 512), 128)) == (0, 0, 230, 77)
        assert atlas.getpixel((int(m.vertices[1].uv[0].u * 512), 128)) == (230, 0, 0, 77)
    assert audit[0]['omitted_secondary_texture'] == 'omitted.dds'
    assert 'Base_Tex_2_SRGB' not in dict(m.materialInstance.textures)
    assert m.vertices[0].position == (1, 2, 3) and m.vertices[0].boneMapping == {'head': 1}


def test_tint_alpha_and_accessory_are_baked_from_the_owners_primary_texture(tmp_path):
    Image.new('RGBA', (256, 256), (200, 100, 50, 128)).save(tmp_path / 'cap_owned.png')
    m = mesh('cap_owned', [(.2, .3), (.8, .7)], (.5, 1, 1, .5), 'pes3DDF_Skin_Face')
    _, audit = build_atlas(dict(hair=Bag(meshes=[m])), tmp_path, tmp_path / 'atlas.png')
    with Image.open(tmp_path / 'atlas.png') as image:
        assert image.getpixel((100, 100)) == (100, 100, 50, 64)
    assert audit[0]['primary_texture'] == 'cap_owned.dds'
    assert m.materialInstance.technique == 'pes3DDF_Hair2'
    (tmp_path / 'cap_owned.png').unlink()
    with pytest.raises(ValueError, match='Missing primary'):
        build_atlas(dict(hair=Bag(meshes=[mesh('cap_owned', [(.2, .3)])])), tmp_path, tmp_path / 'another.png')


def test_shared_vertex_is_remapped_once_but_conflicting_material_mapping_rejected(tmp_path):
    for name in ('hair', 'other'):
        Image.new('RGBA', (256, 256), (20, 30, 40, 255)).save(tmp_path / (name + '.png'))
    m = mesh('hair', [(.5, .5), (1.5, .5)])
    other = Bag(materialInstance=m.materialInstance, vertices=m.vertices)
    build_atlas(dict(face=Bag(meshes=[m, other])), tmp_path, tmp_path / 'same.png')
    assert m.vertices[0].uv[0].u == .25
    m = mesh('hair', [(.5, .5)])
    other = mesh('other', [(.5, .5)])
    other.vertices = m.vertices
    with pytest.raises(ValueError, match='conflicting atlas'):
        build_atlas(dict(face=Bag(meshes=[m, other])), tmp_path, tmp_path / 'conflict.png')


def test_excessive_repeat_or_tint_is_held(tmp_path):
    Image.new('RGBA', (256, 256)).save(tmp_path / 'hair.png')
    with pytest.raises(ValueError, match='extent'):
        build_atlas(dict(face=Bag(meshes=[mesh('hair', [(0, 0), (5, 0)])])), tmp_path, tmp_path / 'large.png')
    with pytest.raises(ValueError, match='tint'):
        build_atlas(dict(face=Bag(meshes=[mesh('hair', [(0, 0)], (float('nan'), 1, 1, 1))])), tmp_path, tmp_path / 'nan.png')


def test_missing_primary_uses_explicit_own_secondary_with_its_own_uv(tmp_path):
    source=Image.new('RGBA',(256,256),(220,0,0,100))
    source.paste((0,0,220,200),(128,0,256,256));source.save(tmp_path/'omitted.png')
    m=mesh('missing',[(.1,.2),(.1,.8)])
    for v in m.vertices:v.uv.append(Bag(u=.75,v=.5))
    _,audit=build_atlas(dict(hair=Bag(meshes=[m])),tmp_path,tmp_path/'atlas.png')
    with Image.open(tmp_path/'atlas.png') as result:
        assert result.getpixel((round(m.vertices[0].uv[0].u*256),128))==(0,0,220,200)
    assert audit[0]['diffuse_policy']=='own_secondary_diffuse_uv1'
    assert audit[0]['source_uv_channel']==1
    assert m.vertices[0].position==(1,2,3) and m.vertices[0].boneMapping=={'head':1}
    for bad in (mesh('missing',[(.2,.3)]),mesh('cap_missing',[(.2,.3)],technique='pes3DDF_Skin_Face')):
        with pytest.raises(ValueError,match='Missing primary'):
            build_atlas(dict(hair=Bag(meshes=[bad])),tmp_path,tmp_path/'bad.png')
