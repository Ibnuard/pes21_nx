"""Bounded reflection-independent approximation for the imported Cup metal.

This uses the prop's own base texture. It is an authored preview material,
not a decoding of Fox packed specular maps or a PC lighting port.
"""
import os


def require_isolated_project(project_dir, expected_dir, repository):
    """Refuse source/runtime projects before editing any Unreal object."""
    actual, expected, root = [os.path.normcase(os.path.realpath(p))
                              for p in (project_dir, expected_dir, repository)]
    allowed = os.path.join(root, 'local-debug') + os.sep
    if actual != expected or not actual.startswith(allowed):
        raise ValueError('Cup material edits require the exact ignored project')
    return actual


CUP_METAL_CODE = r'''
float3 n = normalize(Normal);
float3 v = normalize(View);
float3 l = normalize(float3(-0.35, 0.30, 0.88));
float ndl = saturate(dot(n,l));
float fresnel = pow(1.0-saturate(dot(n,v)),4.0);
float3 halfVector = l+v;
halfVector *= rsqrt(max(dot(halfVector,halfVector),0.0001));
float highlight = pow(saturate(dot(n,halfVector)),48.0);
float shade = 0.42 + 0.30*ndl + 0.15*saturate(n.z);
return min(Base*shade + (0.55*highlight+0.16*fresnel)*(0.5+0.5*Base),1.35);
'''.strip()

MATERIAL_PATH = '/Game/Assets/FootballNX/FixDemo/cup_int_hi/M_gold_ggx_LR'
TEXTURE_PATH = '/Game/Assets/FootballNX/FixDemo/cup_int_hi/T_gold_ggx_LR'


def material_contract():
    return dict(policy='cup-metal-v88', base_texture=TEXTURE_PATH,
                shading='unlit analytic hemisphere, fixed key highlight and view rim',
                reflection_capture_reads=0, texture_reads=1,
                packed_fox_maps_decoded=False, dynamic_lights=0,
                code=CUP_METAL_CODE)
