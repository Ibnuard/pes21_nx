from pathlib import Path
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_loose_cpk import extract, update, verify, NAMES


def table(rows):
    strings = bytearray(b'test\0')
    def string(value):
        offset = len(strings)
        strings.extend(value.encode() + b'\0')
        return offset
    descriptors, values = bytearray(), bytearray()
    columns = list(rows[0])
    types = [10 if isinstance(rows[0][k], str) else 6 for k in columns]
    for key, kind in zip(columns, types):
        descriptors.extend(bytes([0x50 | kind]) + struct.pack('>I', string(key)))
    for row in rows:
        for key, kind in zip(columns, types):
            values.extend(struct.pack('>I', string(row[key])) if kind == 10 else struct.pack('>Q', row[key]))
    row_start = 32 + len(descriptors)
    string_start = row_start + len(values)
    end = string_start + len(strings)
    return struct.pack('>4sIIIIIHHI', b'@UTF', end-8, row_start-8,
                       string_start-8, end-8, 0, len(columns),
                       len(values)//len(rows), len(rows)) + descriptors + values + strings


def cpk(members):
    offset, rows = 1024, []
    for name, payload in members.items():
        rows.append(dict(FileName=name, FileOffset=offset-256,
                         FileSize=len(payload), ExtractSize=len(payload)))
        offset += len(payload)
    def packet(sig, rows):
        data = table(rows)
        return struct.pack('<4s4xQ', sig, len(data)) + data
    header = packet(b'CPK ', [dict(TocOffset=256, ContentOffset=1024)])
    toc = packet(b'TOC ', rows)
    assert len(header) <= 256 and len(toc) <= 768
    return header.ljust(256, b'\0') + toc.ljust(768, b'\0') + b''.join(members.values())


class PackageTests(unittest.TestCase):
    def test_extract_verify_partial_update_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            obb, out = root/'source.obb', root/'package'
            payloads = {n: cpk({'asset.bin': n.encode()}) for n in NAMES}
            obb.write_bytes(cpk(payloads))
            original = hashlib.sha256(obb.read_bytes()).hexdigest()
            result = extract(obb, out, '81f096d278e1225b')
            self.assertEqual(result['source_obb_sha256'], original)
            for n in NAMES:
                self.assertEqual((out/'LooseCpk'/n).read_bytes(), payloads[n])
            with self.assertRaises(ValueError):
                extract(obb, out, '81f096d278e1225b')
            new = root/'new.cpk'
            new.write_bytes(cpk({'asset.bin': b'new database'}))
            result = update(out, NAMES[0], new)
            self.assertEqual(result['changed'], ['LooseCpk/'+NAMES[0], 'LooseCpk/manifest.txt'])
            self.assertEqual((out/'LooseCpk'/NAMES[1]).read_bytes(), payloads[NAMES[1]])
            self.assertEqual(update(out, NAMES[0], new)['changed'], [])
            self.assertEqual(hashlib.sha256(obb.read_bytes()).hexdigest(), original)
            target = out/'LooseCpk'/NAMES[0]
            damaged = bytearray(target.read_bytes())
            damaged[-1] ^= 1
            target.write_bytes(damaged)
            with self.assertRaises(ValueError):
                verify(out, obb)

    def test_invalid_archive_does_not_publish_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            obb = root/'bad.obb'
            obb.write_bytes(cpk({NAMES[0]: b'not a cpk', NAMES[1]: b'bad'}))
            with self.assertRaises((ValueError, RuntimeError)):
                extract(obb, root/'package', '81f096d278e1225b')
            self.assertFalse((root/'package/LooseCpk/manifest.txt').exists())


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.exe = cls.root/'runtime.exe'
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "loose_cpk.h"
#define debugPrintf(...) ((void)0)
#define fatal_error(...) abort()
static int hash_file(const char *path, unsigned char digest[32]) {
 FILE *f=fopen(path,"rb"); if(!f) return 0;
 memset(digest,0,32); fseek(f,4,SEEK_SET); digest[0]=fgetc(f); fclose(f); return 1;
}
static void *seen_source; static const char *seen_path;
static int32_t sound_cri_bind_cpk_original(void *b,void *s,const char *p,void *w,int32_t n,uint32_t *id) {
 assert(b==(void*)1 && w==(void*)3 && n==77); seen_source=s; seen_path=p; *id=9; return 0;
}
'''
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        start = hooks.index('static int32_t pes_runtime_cri_bind_cpk(')
        end = hooks.index('\n}', start) + 2
        source += hooks[start:end]
        source += r'''
int main(int argc,char **argv) {
 char error[256]; int expected=atoi(argv[1]);
 assert(!pes_loose_cpk_path("/Expansion/dt200_mobile_all.cpk"));
 int result=pes_loose_cpk_init("81f096d278e1225b",hash_file,error,sizeof(error));
 if(result!=expected) { fprintf(stderr,"result=%d expected=%d %s",result,expected,error); return 1; }
 uint32_t id=0;
 pes_runtime_cri_bind_cpk((void*)1,(void*)2,"/Expansion/dt200_mobile_all.cpk",(void*)3,77,&id);
 assert(id==9);
 if(result==1) { assert(!seen_source); assert(!strcmp(seen_path,"./LooseCpk/dt200_mobile_all.cpk")); }
 else { assert(seen_source==(void*)2); assert(!strcmp(seen_path,"/Expansion/dt200_mobile_all.cpk")); }
 pes_runtime_cri_bind_cpk((void*)1,(void*)2,"/Expansion/dt240_mobile_all.cpk",(void*)3,77,&id);
 assert(seen_source==(void*)2 && !strcmp(seen_path,"/Expansion/dt240_mobile_all.cpk"));
 pes_runtime_cri_bind_cpk((void*)1,0,"/Expansion/dt200_mobile_all.cpk",(void*)3,77,&id);
 assert(!seen_source && !strcmp(seen_path,"/Expansion/dt200_mobile_all.cpk"));
 assert(!pes_loose_cpk_path("/Other/dt200_mobile_all.cpk"));
 assert(!pes_loose_cpk_path(0));
 return 0;
}
'''
        path = cls.root/'test.c'
        path.write_text(source)
        subprocess.run([compiler, '-std=c11', '-I', str(ROOT/'source'), str(path),
                        str(ROOT/'source/loose_cpk.c'), '-o', str(cls.exe)], check=True, capture_output=True)

    def test_manifest_validation_and_actual_bind_routing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def run(expected):
                subprocess.run([str(self.exe), str(expected)], cwd=root, check=True, capture_output=True)
            run(0)  # Legacy package: no manifest means unchanged binding.
            (root/'LooseCpk').mkdir()
            (root/'patch.305030001.jp.nyan2021.pesam.obb').write_bytes(b'OBB')
            manifest = root/'LooseCpk/manifest.txt'
            text = 'PESNX_LOOSE_CPK_V1 81f096d278e1225b 3\n'
            for n in NAMES:
                (root/'LooseCpk'/n).write_bytes(b'CPK \0')
                text += n+' 5 '+'0'*64+'\n'
            manifest.write_text(text)
            run(1)
            manifest.write_text(text.replace('81f096d278e1225b','0000000000000000'))
            run(-1)
            manifest.write_text(text+'unexpected\n')
            run(-1)
            manifest.write_text(text)
            (root/'LooseCpk'/NAMES[0]).write_bytes(b'CPK \1')  # same-size hash mismatch
            run(-1)
            (root/'LooseCpk'/NAMES[0]).write_bytes(b'CPK')
            run(-1)
            (root/'LooseCpk'/NAMES[0]).unlink()
            run(-1)
