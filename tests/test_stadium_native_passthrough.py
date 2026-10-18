"""The addon loader must never decimate/hide/rebind a fresh native stadium."""
from pathlib import Path
import shutil

import pytest
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


def test_native_loaded_callback_does_not_mutate_any_native_actor_or_mesh():
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('gcc required for native stadium boundary replay')
    build_and_run(cc, r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define PESNX_STADIUM_CANARY_HOST_TEST 1
#define PESNX_SCENE_RUNTIME_LOG_H 1
typedef struct { void *data; int32_t num,max; } Ue4Array;
static char inventory[256];
static uint64_t scene_runtime_ms(void) { return 0; }
static void scene_runtime_note(const char *area,const char *text) {
  if(!strcmp(area,"stadium inventory")) snprintf(inventory,sizeof(inventory),"%s",text);
}
static uint32_t pes_controller_2p_prematch_hub_stadium_index(void) { return 0; }
''' + f'#include "{(ROOT / "source/stadium_canary.inc").as_posix()}"\n' + r'''
static unsigned native_calls;
static void original(void *loader) { ++native_calls; }
static void *actor_class(void) { return (void *)11; }
static void *component_class(void) { return (void *)12; }
static unsigned char actors[3][0x200],components[3][0x600],meshes[3][0x100];
static unsigned char actor_copy[sizeof actors],component_copy[sizeof components],mesh_copy[sizeof meshes];
static void get_actors(const void *world,void *cls,Ue4Array *out) {
  assert(world==(void *)13 && cls==(void *)11);
  void **list=malloc(sizeof(void *)*3);
  for(unsigned i=0;i<3;++i) list[i]=actors[i];
  *out=(Ue4Array){list,3,3};
}
static void get_name(const void *p,Ue4Array *out) {
  const char *name=p;const size_t len=strlen(name)+1;
  uint16_t *wide=malloc(len*2);
  for(unsigned i=0;i<len;++i) wide[i]=(unsigned char)name[i];
  *out=(Ue4Array){wide,(int)len,(int)len};
}
int main(void) {
  void *world=(void *)13;stadium_world=&world;
  stadium_loaded_original=original;stadium_get_actors=get_actors;
  stadium_actor_class=actor_class;stadium_component_class=component_class;
  stadium_fname_string=get_name;stadium_engine_free=free;
  // ALL mutation/asset-load callbacks remain NULL. Any accidental write path fails.
  for(unsigned pass=0;pass<2;++pass) {
    memset(actors,0x5a,sizeof actors);memset(components,0x5a,sizeof components);
    memset(meshes,0x5a,sizeof meshes);
    const char *names[]={pass?"st029_b_low":"st029_b","st029_c","st029_pitch"};
    for(unsigned i=0;i<3;++i) {
      void *component=components[i],*mesh=meshes[i],*cls=(void *)12;
      memcpy(actors[i]+0x158,&component,sizeof component);
      memcpy(components[i]+0x10,&cls,sizeof cls);
      memcpy(components[i]+0x5b0,&mesh,sizeof mesh);
      strcpy((char *)meshes[i]+0x18,names[i]);
    }
    memcpy(actor_copy,actors,sizeof actors);memcpy(component_copy,components,sizeof components);
    memcpy(mesh_copy,meshes,sizeof meshes);
    stadium_canary_active=13;
    stadium_loaded_canary(NULL);
    assert(stadium_canary_active==0 && native_calls==pass+1);
    assert(!memcmp(actor_copy,actors,sizeof actors));
    assert(!memcmp(component_copy,components,sizeof components));
    assert(!memcmp(mesh_copy,meshes,sizeof meshes));
    assert(strstr(inventory,"requested=0 static_actors=3 native_shells=2 imported_shells=0"));
    assert(strstr(inventory,pass?"carrier=0":"carrier=1"));
  }
}
''')
