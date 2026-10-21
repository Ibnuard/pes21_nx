"""Actual bounded native-layout guards and cancel-safe presentation predicate."""
from pathlib import Path
import shutil
import subprocess

import pytest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def test_guarded_offside_snapshot_clears_on_end_cancel_and_null_owner(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    source = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "referee_presentation.h"
typedef struct {uintptr_t load_base,load_virtbase;size_t load_size;} so_module;
static unsigned char code[0x800],registry[0x410],demo[0x80],fixed[0x30];
static uint32_t referee_presentation_layout_ok;
static uintptr_t symbols[6];
static uintptr_t so_try_find_addr_rx(so_module *m,const char *n){
 (void)m;
 if(strstr(n,"GetFixDemoId"))return symbols[0];
 if(strstr(n,"IsFixDemoExec"))return symbols[1];
 if(strstr(n,"getDemoSceneInfoAdr"))return symbols[2];
 if(strstr(n,"chkIsOffsideGoalStartScene"))return symbols[3];
 if(strstr(n,"ExecDemo"))return symbols[4];
 if(strstr(n,"CheckDemoTypeFoulJudgement"))return symbols[5];
 return 0;
}
static void scene_runtime_note(const char *a,const char *b){assert(a && b);}
static void *get_registry(void){return registry;}
static void *(*match_global_registry_get_instance)(void)=get_registry;
''' + "\n".join(function(hooks, n) for n in (
        "referee_presentation_code", "referee_presentation_install",
        "referee_offside_presentation_active")) + r'''
static void put32(unsigned char *p,uint32_t v){memcpy(p,&v,4);}
int main(void){
 so_module m={(uintptr_t)code,(uintptr_t)0x10000000,sizeof(code)};
 for(unsigned i=0;i<6;i++)symbols[i]=m.load_virtbase+i*0x100u;
 const uint32_t id[]={0xb9400000,0xd65f03c0},exec[]={0x3941f400,0xd65f03c0};
 const uint32_t scene[]={0x91005000,0xd65f03c0};
 const uint32_t classifier[]={0x52802f48,0x72a00068,0x6b08001f,0x1a9f17e0,0xd65f03c0};
 memcpy(code,id,sizeof(id));memcpy(code+0x100,exec,sizeof(exec));
 memcpy(code+0x200,scene,sizeof(scene));memcpy(code+0x300,classifier,sizeof(classifier));
 put32(code+0x508,0xf941b119);put32(code+0x510,0xf9400108);
 put32(code+0x514,0xf9420108);put32(code+0x53c,0xb9400c00);
 /* Flow's +108 and sound's +10 overlap independent synthetic symbol spans. */
 symbols[4]=m.load_virtbase+0x600;put32(code+0x708,0xf941b119);
 referee_presentation_install(&m);assert(referee_presentation_layout_ok);
 unsigned char *p=demo;memcpy(registry+0x360,&p,sizeof(p));
 p=fixed;memcpy(registry+0x400,&p,sizeof(p));
 assert(!referee_offside_presentation_active());
 put32(demo,0x3017a);put32(fixed+0x20,0x3017a);demo[0x7d]=1;
 assert(referee_offside_presentation_active());
 demo[0x7d]=0;assert(!referee_offside_presentation_active());demo[0x7d]=1;
 /* Cancel clears the current scene before the exec bit gets reinitialized. */
 put32(fixed+0x20,0);assert(!referee_offside_presentation_active());
 put32(fixed+0x20,0x20001);assert(!referee_offside_presentation_active());
 put32(fixed+0x20,0x3017a);put32(demo,0x20001);assert(!referee_offside_presentation_active());
 put32(demo,0x3017a);assert(referee_offside_presentation_active());
 p=NULL;memcpy(registry+0x400,&p,sizeof(p));assert(!referee_offside_presentation_active());
 assert(!referee_offside_presentation(NULL));
 const unsigned sites[]={0,0x100,0x200,0x300,0x708,0x510,0x514,0x53c};
 for(unsigned i=0;i<sizeof(sites)/sizeof(sites[0]);i++){
  code[sites[i]]^=1;referee_presentation_install(&m);assert(!referee_presentation_layout_ok);
  code[sites[i]]^=1;referee_presentation_install(&m);assert(referee_presentation_layout_ok);
 }
 symbols[0]=0;referee_presentation_install(&m);assert(!referee_presentation_layout_ok);
 symbols[0]=m.load_virtbase+m.load_size-4;referee_presentation_install(&m);assert(!referee_presentation_layout_ok);
 symbols[0]=m.load_virtbase-4;referee_presentation_install(&m);assert(!referee_presentation_layout_ok);
 referee_presentation_install(NULL);assert(!referee_presentation_layout_ok);
}
'''
    path = tmp_path / "offside.c"
    path.write_text(source)
    exe = tmp_path / "offside.exe"
    subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "source"), str(path), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
