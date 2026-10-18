"""Verify early RGB sampling rejection in project-authored cooked shells.

All compiled shader inputs stay local. Only normalized body fingerprints are
written to the optional public registry; no extracted shader source is saved.
Runs the actual C policy and validates all clip/HDR permutations with glslang.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]


def fragments(path):
    data=path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]',data):
        try: block=zlib.decompress(data[match.start():])
        except zlib.error: continue
        if not block.startswith(b'LSLGSP'): continue
        start=block.find(b'#version');end=block.find(b'\0',start)
        if start>=0 and end>start:
            yield block[start:end].replace(b'\r\n',b'\n')


def fingerprint(source):
    body=source[source.index(b'void main()'):]
    value=14695981039346656037
    for byte in body:
        if byte in b' \t\r\n': continue
        value=((value^byte)*1099511628211)&0xffffffffffffffff
    return value


def verify_order(original,changed):
    a=original[original.index(b'void main()'):]
    b=changed[changed.index(b'void main()'):]
    marker=b.index(b'nxShellEarlyClip')
    discard=b.rindex(b'discard;')
    fetch=b.index(b'textureGrad(',discard)
    assert marker<b.index(b'nxShellColorDx=')<discard<fetch
    # Coverage, output and native uniforms must be retained verbatim.
    before=re.findall(rb'[^\n]*discard;',a)
    after=re.findall(rb'[^\n]*discard;',b)
    assert before==after
    assert a[a.rindex(b'discard;')+8:]==b[b.index(b'\n',fetch)+1:]
    assert changed.count(b'texture')==original.count(b'texture')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cooked',type=Path,required=True)
    p.add_argument('--profiles',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--validator',type=Path,required=True)
    p.add_argument('--register',action='store_true')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    driver=a.work/'shell-clip-transform.c';exe=driver.with_suffix('.exe')
    template='#include "stadium_shell_clip.h"\nint main(void){char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;char*p=FUNCTION(s);if(!p)return 2;fputs(p,stdout);free(p);return 0;}\n'
    def build(function):
        driver.write_text(template.replace('FUNCTION',function))
        subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(driver),'-o',str(exe)],check=True)
    build('stadium_shell_clip_transform')
    records=[];material_count=0
    for profile in sorted(a.profiles.glob('*/fbx.local.json')):
        data=json.loads(profile.read_text());key=data['key']
        for name in data['material_slots']:
            path=a.cooked/'PesMobile/Content/FootballNX/Stadiums'/key/(name+'.uexp')
            material_count+=1
            for source in fragments(path):
                result=subprocess.run([str(exe)],input=source,capture_output=True)
                if result.returncode==2: continue
                if result.returncode: raise RuntimeError(result.stderr.decode(errors='replace'))
                verify_order(source,result.stdout)
                records.append((key+'/'+name,source,result.stdout))
    assert records,'No eligible authored shell shaders'
    registry=ROOT/'source/stadium_shell_clip_fingerprints.inc'
    known={int(v,16) for v in re.findall(r'UINT64_C\(0x([0-9a-f]+)\)',registry.read_text())}
    hashes={fingerprint(source) for _,source,_ in records}
    if a.register:
        known|=hashes
        registry.write_text('/* Normalized bodies of verified, project-authored ES3.1 shell shaders. */\n'+
            ''.join('UINT64_C(0x%016x),\n'%h for h in sorted(known)))
    assert hashes<=known,'Register audited authored shader bodies before packaging'
    build('stadium_shell_clip_source')
    jobs={}
    for label,source,changed in records:
        actual=subprocess.run([str(exe)],input=source,capture_output=True,check=True).stdout.replace(b'\r\n',b'\n')
        assert actual==changed
        for text in (source,changed):
            for clip in range(2):
                for hdr in range(4):
                    at=text.index(b'\n')
                    macro=('\n#define HLSLCC_DX11ClipSpace %d\n#define HDR_32BPP_ENCODE_MODE %.1f\n#define INTERFACE_LOCATION(X) layout(location=X)\n'%(clip,hdr)).encode()
                    shader=text[:at]+macro+text[at:]
                    jobs[hashlib.sha256(shader).hexdigest()]=(label,shader)
    def compile_shader(row):
        label,shader=row
        result=subprocess.run([str(a.validator),'--stdin','-S','frag'],input=shader,capture_output=True)
        return None if result.returncode==0 else dict(material=label,error=(result.stdout+result.stderr).decode(errors='replace'))
    with ThreadPoolExecutor(max_workers=4) as pool:errors=[e for e in pool.map(compile_shader,jobs.values()) if e]
    summary=dict(materials=material_count,transformed_records=len(records),body_fingerprints=len(hashes),registry_entries=len(known),unique_compiles=len(jobs),errors=errors,
        policy='RGB fetch follows unchanged camera/alpha discard; gradients computed before discard; ES2 and unknown bodies unchanged; not a GPU benchmark')
    (a.work/'shell-clip-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary));assert not errors,errors[:2]


if __name__=='__main__':main()
