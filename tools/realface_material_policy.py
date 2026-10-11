"""Classify source material roles from shader/texture metadata, not labels.

A file called hair may contain the main skin, and fox_skin_mat may be a wet
overlay or a hair shader. Multi-texture hair is flagged for an explicit local
bake/texture policy; classification alone does not port that shader.
"""
import argparse
import json
from pathlib import Path, PurePosixPath


def classify(material):
    extras=material['extras']
    technique=extras['fmdlTechnique']
    textures={t['role']:PurePosixPath(t['filename']).name for t in extras['fmdlTextures']}
    base=textures.get('Base_Tex_SRGB','').lower()
    if technique in ('pes3DDC_Wet','pes3DDC_Adjust_100'):
        role='effect'
    elif technique=='pes3DFW_EyeOcclusion':
        role='eyelid_guide'
    elif technique.startswith('pes3DDF_Hair'):
        role='hair'
    elif technique in ('pes3DDF_Skin_Face','fox3DDF_Blin') and base=='face_bsm_alp.dds':
        role='skin'
    else:
        role='unsupported_auxiliary'
    return dict(name=material['name'],technique=technique,role=role,textures=textures,
                requires_texture_bake=role=='hair' and 'Base_Tex_2_SRGB' in textures)


def plan_parts(documents):
    return {part:[classify(m) for m in document['materials']]
            for part,document in documents.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--face-gltf',type=Path,required=True)
    parser.add_argument('--hair-gltf',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    result=plan_parts({part:json.loads(path.read_text(encoding='utf-8'))
                       for part,path in [('face',args.face_gltf),('hair',args.hair_gltf)]})
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
