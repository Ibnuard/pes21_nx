"""Prepare the optional scoreboard OBB without changing its external size.

The existing roster/portrait OBB is the base. Only dt210's game2dPes atlas is
replaced. Every other member is compared byte-for-byte after packing.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from prepare_runtime import read_cpk_packet
from patch_cpk_slots import member_name, patch_slot


def table(path):
    with path.open('rb') as f:
        h=read_cpk_packet(f,0,b'CPK ')[0]
        return h,read_cpk_packet(f,h['TocOffset'],b'TOC ')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base-obb',type=Path,default=Path('dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb'))
    p.add_argument('--skin',type=Path,default=Path('local-debug/stability-visuals/built/game2dPes.bin'))
    p.add_argument('--output',type=Path,default=Path('local-debug/stability-test-20260830/patch.305030001.jp.nyan2021.pesam.obb'))
    p.add_argument('--work',type=Path,default=Path('local-debug/stability-visuals/package'))
    a=p.parse_args()
    if a.output.exists():
        raise ValueError('refusing to overwrite existing candidate')
    a.work.mkdir(parents=True,exist_ok=True)
    h,rows=table(a.base_obb)
    row=next(r for r in rows if r['FileName']=='dt210_mobile_android.cpk')
    base=min(h['TocOffset'],h['ContentOffset'])
    original=a.work/'dt210-original.cpk'
    with a.base_obb.open('rb') as f,original.open('wb') as o:
        f.seek(base+row['FileOffset'])
        remaining=row['FileSize']
        while remaining:
            data=f.read(min(4*1024*1024,remaining))
            if not data:
                raise ValueError('truncated OBB')
            o.write(data)
            remaining-=len(data)
    patched=a.work/'dt210-score.cpk'
    subprocess.run([sys.executable,str(Path(__file__).with_name('repack_cpk_members.py')),
                    str(original),str(patched),'--expect-members','422',
                    '--replace','common/menu/licence/game2dPes.bin='+str(a.skin)],check=True)
    # The generic repacker aligns EOF upward. Discard only verified unused
    # terminal zero padding, retaining the original outer member size.
    ph,pr=table(patched)
    data_base=min(ph['TocOffset'],ph['ContentOffset'])
    maximum=max(data_base+r['FileOffset']+r['FileSize'] for r in pr)
    if maximum>row['FileSize']:
        raise ValueError('repacked dt210 needs a larger OBB; do not install')
    with patched.open('r+b') as f:
        f.seek(row['FileSize'])
        if any(f.read()):
            raise ValueError('nonzero terminal data; refuse truncation')
        f.truncate(row['FileSize'])
    # Validate all 421 unrelated inner CPK members too.
    oh,old_rows=table(original)
    old_base=min(oh['TocOffset'],oh['ContentOffset'])
    with original.open('rb') as old,patched.open('rb') as new:
        for before,after in zip(old_rows,pr):
            assert before['FileName']==after['FileName'] and before['DirName']==after['DirName']
            if before['FileName']=='game2dPes.bin':
                continue
            assert before['FileSize']==after['FileSize'] and before['ExtractSize']==after['ExtractSize']
            old.seek(old_base+before['FileOffset'])
            new.seek(data_base+after['FileOffset'])
            assert old.read(before['FileSize'])==new.read(after['FileSize'])
    report=patch_slot(a.base_obb,a.output,member_name(row),patched)
    report['unrelated_dt210_members_byte_identical']=421
    report['all_team_roster_and_portrait_data_unchanged']=True
    (a.output.parent/'scoreboard-package-validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
