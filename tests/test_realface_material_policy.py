import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_material_policy import classify, plan_parts


def material(name, technique, textures):
    return {
        'name': name,
        'extras': {
            'fmdlTechnique': technique,
            'fmdlTextures': [
                {'role': role, 'filename': filename}
                for role, filename in textures.items()
            ],
        },
    }


def test_head_in_hair_file_and_wet_layer_in_face_are_distinguished():
    parts = plan_parts({
        'hair': {'materials': [material('fox_skin_mat', 'fox3DDF_Blin', {
            'Base_Tex_SRGB': 'textures/face_bsm_alp.dds',
        })]},
        'face': {'materials': [material('fox_skin_mat', 'pes3DDC_Wet', {
            'Base_Tex_SRGB': 'textures/face_bsm_alp.dds',
        })]},
    })
    assert parts['hair'][0]['role'] == 'skin'
    assert parts['face'][0]['role'] == 'effect'


def test_skin_label_does_not_override_hair_shader_or_bake_requirement():
    result = classify(material('fox_skin_mat', 'pes3DDF_Hair', {
        'Base_Tex_SRGB': 'face_bsm_alp.dds',
        'Base_Tex_2_SRGB': 'hair_bsm_alp.dds',
    }))
    assert result['role'] == 'hair'
    assert result['requires_texture_bake'] is True


def test_unknown_skin_label_is_not_accepted_as_head_geometry():
    result = classify(material('fox_skin_mat', 'unknown_shader', {
        'Base_Tex_SRGB': 'face_bsm_alp.dds',
    }))
    assert result['role'] == 'unsupported_auxiliary'
