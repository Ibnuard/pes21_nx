"""Exact aliases for the generated, proven invisible native hair slot.

Blender disambiguates an existing material as .001; FBX/UE may spell that
suffix _001. This is not a general material-name or role guessing policy.
Kept dependency-free for the UE editor's bundled Python.
"""
import json
import io
import os


def invisible_hair_aliases(profile):
    if (profile.get('opaque_eye_atlas') is not True or
            profile.get('hair_materials') != ['lite_hair'] or
            profile.get('hair_skin_materials') != []):
        return {}
    folder = os.path.dirname(profile['hair_fbx'])
    if os.path.dirname(profile['hair_texture']) != folder:
        return {}
    path = os.path.join(folder,'invisible-source-slot-proof.json')
    if not os.path.isfile(path):
        return {}
    with io.open(path,encoding='utf-8') as stream:
        proof = json.load(stream)
    if (proof.get('policy') != 'proven_alpha_hidden_or_rigid_microscopic_source_slot_v1' or
            proof.get('unproven') != 0 or proof.get('replacement_triangles') != 1 or
            proof.get('source_skin_changed') is not False or
            proof.get('visible_source_removed') is not False):
        raise ValueError('Invalid invisible native slot proof')
    return {'lite_hair_001': 'lite_hair', 'lite_hair.001': 'lite_hair'}
