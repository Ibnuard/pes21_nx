"""Render the eight cached canary atlases without rebuilding archives."""
import argparse
from pathlib import Path
from PIL import Image
from kit_preview_mesh import render_mesh, build_mesh, export_obj
from build_kit_preview_canary import write_contact_sheet


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--atlases',type=Path,default=Path('local-debug/kit-preview-canary-v3/atlases'))
    parser.add_argument('--output',type=Path,default=Path('local-debug/kit-preview-mesh-review'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    mesh=build_mesh()
    export_obj(args.output/'jersey.obj',mesh)
    rows=[]
    for tid,name in [(100,'Manchester United'),(108,'FC Barcelona'),(109,'Real Madrid'),(173,'Manchester City')]:
        row=dict(team_id=tid,name=name,kits=[])
        for suffix in ('p1','p2'):
            with Image.open(args.atlases/str(tid)/(suffix+'.png')) as image:
                preview=render_mesh(image,mesh)
            target=args.output/f'{tid}-{suffix}.png'
            preview.save(target)
            row['kits'].append(dict(preview_path=str(target),suffix=suffix))
        rows.append(row)
    write_contact_sheet(rows,args.output/'contact-sheet.png')
    print(args.output/'contact-sheet.png')


if __name__=='__main__':
    main()
