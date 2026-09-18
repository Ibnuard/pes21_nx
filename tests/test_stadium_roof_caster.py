"""Exact roof identity, live shadow gating and native-proxy lifecycle guards."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text()
POLICY = (ROOT / 'source/stadium_roof_policy.h').read_text()


class RoofCasterTests(unittest.TestCase):
    def run_c(self, text):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('gcc unavailable')
        build_and_run(cc, '#include <assert.h>\n' + POLICY + text)

    def test_roof_is_always_off_without_a_toggle(self):
        self.run_c(function(SOURCE, 'pes_controller_roof_shadow_enabled') + r'''
int main(void) {
  assert(!pes_controller_roof_shadow_enabled());
  for (unsigned i=0;i<100;++i) {
    assert(pes_controller_roof_shadow_enabled()==0);
  }
}
''')
        self.assertNotIn('uint32_t stadium_roof_shadow_enabled', SOURCE)
        overlay = (ROOT / 'source/overlay.c').read_text()
        self.assertNotIn('"ENABLE ROOF SHADOW"', overlay)
        self.assertNotIn('pes_controller_roof_shadow_enabled() ? "ON" : "OFF"', overlay)
        self.assertIn('const uint32_t rows = 2u;',
                      function(SOURCE, 'pes_controller_2p_prematch_hub_pad_event'))

    def test_exact_asset_and_bounded_registry(self):
        self.run_c(r'''
static unsigned identify(const char *s) {
  uint16_t path[256]; size_t n = strlen(s);
  for (size_t i=0; i<=n; ++i) path[i]=(unsigned char)s[i];
  return stadium_roof_mesh_id(path,n+1);
}
int main(void) {
  assert(identify("/Game/Assets/bg_lighting_AM1/Meshes/st029_c.st029_c")==1);
  assert(identify("/Game/Assets/bg_lighting_AM1/Meshes/st029_c_glass.st029_c_glass")==2);
  assert(!identify("/Game/Assets/bg_lighting_AM1/Meshes/st029_c_backface.st029_c_backface"));
  assert(!identify("/Game/Assets/bg_lighting_AM1/Meshes/frame.frame"));
  assert(!identify("/Game/Assets/bg_lighting_AM2/Meshes/st029_c.st029_c"));
  assert(!identify("/Game/Assets/bg_lighting_AM1/Meshes/st029_c.st029_c_1"));
  uint16_t invalid[256]={0}; assert(!stadium_roof_mesh_id(invalid,257));
  assert(!stadium_roof_mesh_id(NULL,0));
  StadiumRoofProxies p={0};
  assert(!stadium_roof_remember(&p,0));
  for (unsigned i=1;i<=STADIUM_ROOF_PROXY_SLOTS;i++) {
    assert(stadium_roof_remember(&p,i));
    assert(stadium_roof_remember(&p,i)); // duplicate does not consume slots
  }
  assert(!stadium_roof_remember(&p,100)); // fail open, no eviction
  stadium_roof_forget(&p,7);
  assert(!stadium_roof_contains(&p,7));
  assert(stadium_roof_remember(&p,100));
  assert(stadium_roof_contains(&p,100));
}
''')

    def test_live_day_only_filter_preserves_other_objects_and_reused_addresses(self):
        self.run_c(r'''
static StadiumRoofProxies stadium_roof_proxies;
static uintptr_t stadium_roof_proxy_vtable=42;
static unsigned day,roof,calls,destroyed,deleted;
static unsigned pes_controller_stadium_is_day(void) {return day;}
static unsigned pes_controller_roof_shadow_enabled(void) {return roof;}
static void pes_stadium_shadow_filter_original(void *packet,const void *bounds,
    uint64_t flags,void *info,const void *proxy) {
  assert(packet==(void*)1 && bounds==(void*)2 && flags==0x8765432100000007ULL);
  assert(info==(void*)3 && proxy); ++calls;
}
static void destroy(void *p) {
  assert(!stadium_roof_contains(&stadium_roof_proxies,(uintptr_t)p)); ++destroyed;
}
static void delete_proxy(void *p) {
  assert(!stadium_roof_contains(&stadium_roof_proxies,(uintptr_t)p)); ++deleted;
}
static void (*stadium_mesh_destroy_original)(void *)=destroy;
static void (*stadium_mesh_delete_original)(void *)=delete_proxy;
''' + function(SOURCE, 'pes_stadium_shadow_filter') +
            function(SOURCE, 'pes_stadium_mesh_destroy') +
            function(SOURCE, 'pes_stadium_mesh_delete') + r'''
int main(void) {
  uintptr_t proxy=42,other=42;
  assert(stadium_roof_remember(&stadium_roof_proxies,(uintptr_t)&proxy));
  for (day=0;day<2;++day) for (roof=0;roof<2;++roof) {
    calls=0;
    pes_stadium_shadow_filter((void*)1,(void*)2,0x8765432100000007ULL,(void*)3,&proxy);
    assert(calls==(!day || roof));
    calls=0;
    pes_stadium_shadow_filter((void*)1,(void*)2,0x8765432100000007ULL,(void*)3,&other);
    assert(calls==1); // even another static mesh stays native
  }
  day=1;roof=0;calls=0;proxy=43; // address reused by a different proxy class
  pes_stadium_shadow_filter((void*)1,(void*)2,0x8765432100000007ULL,(void*)3,&proxy);
  assert(calls==1);
  proxy=42; pes_stadium_mesh_destroy(&proxy); assert(destroyed==1);
  calls=0;
  pes_stadium_shadow_filter((void*)1,(void*)2,0x8765432100000007ULL,(void*)3,&proxy);
  assert(calls==1);
  stadium_roof_remember(&stadium_roof_proxies,(uintptr_t)&proxy);
  pes_stadium_mesh_delete(&proxy); assert(deleted==1);
}
''')

    def test_create_copies_identity_then_frees_native_string_and_clears_reuse(self):
        self.run_c(r'''
typedef struct {void *data; int32_t num,max;} Ue4Array;
static StadiumRoofProxies stadium_roof_proxies;
static uintptr_t proxy=42;
static unsigned use_roof=1,freed;
static void *create(void *component) {assert(component); return &proxy;}
static void path(const void *mesh,const void *stop,Ue4Array *out) {
  assert(mesh==(void*)9 && !stop);
  static uint16_t buf[128];
  const char *p=use_roof ? "/Game/Assets/bg_lighting_AM1/Meshes/st029_c.st029_c" : "Unknown";
  out->num=out->max=strlen(p)+1; out->data=buf;
  for (int i=0;i<out->num;++i) buf[i]=p[i];
}
static void free_string(void *p) {assert(p);++freed;}
static void *(*stadium_mesh_create_original)(void*)=create;
static void (*stadium_mesh_path)(const void*,const void*,Ue4Array*)=path;
static void (*stadium_string_free)(void*)=free_string;
#define debugPrintf(...) ((void)0)
''' + function(SOURCE, 'pes_stadium_mesh_create') + r'''
int main(void) {
  unsigned char component[0x5b8]={0}; void *mesh=(void*)9;
  memcpy(component+0x5b0,&mesh,sizeof(mesh));
  assert(pes_stadium_mesh_create(component)==&proxy);
  assert(freed==1 && stadium_roof_contains(&stadium_roof_proxies,(uintptr_t)&proxy));
  use_roof=0; assert(pes_stadium_mesh_create(component)==&proxy);
  assert(freed==2 && !stadium_roof_contains(&stadium_roof_proxies,(uintptr_t)&proxy));
}
''')
