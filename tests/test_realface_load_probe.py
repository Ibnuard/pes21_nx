"""Distinguish a native failed face load from a successful mesh snapshot."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


class FaceLoadProbeTests(unittest.TestCase):
    def test_snapshots_are_bounded_and_only_explicit_reporting_writes(self):
        cc=shutil.which('gcc')
        if not cc: self.skipTest('host gcc unavailable')
        build_and_run(cc,r'''
#define NEAR_CAMERA_TRACE 1
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {int unused;} so_module;
static unsigned writes,calls,miss;
static uintptr_t slots[3]={100,100,100};
static uintptr_t so_try_find_addr_rx(so_module *m,const char *n) {(void)m;(void)n;return 100;}
static uintptr_t *find_vtable_method_slot(so_module *m,const char *n,uintptr_t fn,uint32_t count) {
  (void)m;(void)fn;assert(count==224); unsigned i=strstr(n,"Lowest")?2:strstr(n,"Low")?1:0;
  return miss==i+1?NULL:&slots[i];
}
static uint64_t armGetSystemTick(void) {static uint64_t tick;return ++tick;}
static uint64_t armTicksToNs(uint64_t tick) {return tick*1000;}
static void scene_runtime_note(const char *area,const char *line) {
  assert(!strcmp(area,"realface-load")); ++writes;
  if(writes==1) {
    assert(strstr(line,"native_id=34493") && strstr(line,"face_resolved=0"));
    assert(strstr(line,"hair_resolved=1") && strstr(line,"hair_lods=1"));
  }
  if(writes==2) assert(strstr(line,"hair_mesh=1") && strstr(line,"hair_lods=2"));
  if(writes==3) assert(strstr(line,"hair_mesh=1") && strstr(line,"hair_lods=1"));
}
static void original(void *a,const char *n) {(void)a;(void)n;++calls;}
'''+'#include "'+(ROOT/'source/realface_load_probe.inc').as_posix()+'"\n'+r'''
int main(void) {
  so_module m={0}; miss=2; install_realface_load_probe(&m);
  assert(slots[0]==100 && slots[1]==100 && slots[2]==100);
  miss=0;install_realface_load_probe(&m);assert(slots[0]!=(uintptr_t)100);
  realface_load_original=original;
  unsigned char actor[0x400]={0},comp[0x700]={0},mesh[0x80]={0},render[32]={0};
  void *p=comp;memcpy(actor+0x370,&p,sizeof(p));
  p=mesh;memcpy(actor+0x378,&p,sizeof(p));memcpy(comp+0x6c0,&p,sizeof(p));
  p=render;memcpy(mesh+0x40,&p,sizeof(p));unsigned lod=1;memcpy(render+8,&lod,4);
  realface_load_probe(actor,"34493");
  /* Normal native SetSkeletalMesh writes 0x5a0, not the optional override. */
  p=NULL;memcpy(comp+0x6c0,&p,sizeof(p));
  p=mesh;memcpy(comp+0x5a0,&p,sizeof(p));
  lod=2;memcpy(render+8,&lod,4);realface_load_probe(actor,"34493");
  /* If both exist, the override must win over the regular mesh. */
  unsigned char override_mesh[0x80]={0},override_render[32]={0};
  p=override_mesh;memcpy(comp+0x6c0,&p,sizeof(p));
  p=override_render;memcpy(override_mesh+0x40,&p,sizeof(p));
  lod=1;memcpy(override_render+8,&lod,4);
  for(unsigned i=3;i<=140;++i)realface_load_probe(actor,"34493");
  assert(calls==140 && !writes);pes_controller_face_probe_report();assert(writes==128);
  pes_controller_face_probe_report();assert(writes==128);
}
''')
