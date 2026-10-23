#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#include "corner_tactics.h"
typedef struct {void *load_base,*load_virtbase;size_t load_size;} so_module;
typedef struct {char name[256];uint32_t offset,bytes;} Symbol;
static Symbol symbols[16];
static unsigned symbol_count,lookups,notes,slot_checks;
static int fault;
static uint64_t scene_runtime_ms(void){return 1000;}
static void scene_runtime_note(const char *a,const char *b){assert(a&&b);notes++;}
static int pes_controller_native_pad_lab_active(void){return 0;}
static int pes_controller_native_pad_lab_two_player(void){return 0;}
static uint32_t match_hud_session_serial;
static void *(*match_global_registry_get_instance)(void);
static const void *(*match_global_registry_get_team_ai_info)(const void *,uint32_t);
static uintptr_t so_try_find_addr_rx(so_module *m,const char *name) {
  lookups++;
  for(unsigned i=0;i<symbol_count;i++)if(!strcmp(name,symbols[i].name)) {
    if(i==0 && fault==1)return 0;
    if(i==0 && fault==2)return (uintptr_t)m->load_virtbase-1;
    if(i==0 && fault==3)return (uintptr_t)m->load_virtbase+m->load_size-1;
    if(i==0 && fault==4)return (uintptr_t)m->load_virtbase+m->load_size;
    if(i==9 && fault==7)return (uintptr_t)m->load_virtbase+m->load_size-8;
    if(i==10 && fault==8)return 0;
    return (uintptr_t)m->load_virtbase+symbols[i].offset;
  }
  return 0;
}
static uintptr_t *find_vtable_method_slot(so_module *m,const char *n,uintptr_t method,uint32_t count) {
  assert(strstr(n,"DefenceTypeE") && count==20);slot_checks++;
  uintptr_t *table=(uintptr_t *)((char *)m->load_base+symbols[10].offset);
  for(uint32_t i=2;i<count;i++)if(table[i]==method)return table+i;
  return NULL;
}
#include "corner_tactics_native.inc"
static void *dummy_registry(void){return NULL;}
static const void *dummy_ai(const void *p,uint32_t n){(void)p;(void)n;return NULL;}
static void read_exact(FILE *f,void *p,size_t n){assert(fread(p,1,n,f)==n);}
int main(int argc,char **argv) {
  (void)&corner_native_observe;
  assert(argc==3);fault=atoi(argv[2]);
  unsigned char *backing=calloc(1,65536);assert(backing);
#ifdef _WIN32
  void *rx=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);assert(rx);
#else
  void *rx=mmap(NULL,65536,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(rx!=MAP_FAILED);
#endif
  FILE *f=fopen(argv[1],"rb");assert(f);
  read_exact(f,&symbol_count,4);assert(symbol_count==11);
  for(unsigned i=0;i<symbol_count;i++) {
    uint32_t len;read_exact(f,&len,4);assert(len<sizeof(symbols[i].name));
    read_exact(f,symbols[i].name,len);
    read_exact(f,&symbols[i].offset,4);read_exact(f,&symbols[i].bytes,4);
    assert(symbols[i].offset+symbols[i].bytes<=65536);
    read_exact(f,backing+symbols[i].offset,symbols[i].bytes);
  }
  assert(fgetc(f)==EOF);fclose(f);
  uintptr_t *table=(uintptr_t *)(backing+symbols[10].offset);
  const uintptr_t original=(uintptr_t)rx+symbols[2].offset;
  table[4]=fault==6 ? 0 : original;
  if(fault==5)backing[symbols[0].offset]^=1;
  unsigned char *expected=malloc(65536);assert(expected);memcpy(expected,backing,65536);
  so_module module={backing,rx,65536};
  match_global_registry_get_instance=dummy_registry;
  match_global_registry_get_team_ai_info=dummy_ai;
  if(fault==9)module.load_base=NULL;
  if(fault==10)module.load_virtbase=NULL;
  if(fault==11)module.load_size=16;
  install_corner_tactics(&module);
  assert(notes==1);
  if(!fault) {
    assert(corner_native_enabled && slot_checks==1);
    assert(table[4]==(uintptr_t)&corner_native_defence_main);
    assert((uintptr_t)corner_defence_original==original);
    assert(corner_native_vptr[0]==(uintptr_t)rx+symbols[9].offset+16);
    assert(corner_native_vptr[1]==(uintptr_t)rx+symbols[10].offset+16);
    assert((uintptr_t)corner_get_anime==(uintptr_t)rx+symbols[7].offset);
    assert((uintptr_t)corner_is_setplay_anime==(uintptr_t)rx+symbols[8].offset);
    memcpy(expected+symbols[10].offset+4*sizeof(uintptr_t),table+4,sizeof(uintptr_t));
  } else assert(!corner_native_enabled && table[4]==(fault==6 ? 0 : original));
  assert(!memcmp(expected,backing,65536)); /* Only the admitted RW slot changes. */
  assert(fault<9 || !lookups);
  free(expected);free(backing);
#ifdef _WIN32
  assert(VirtualFree(rx,0,MEM_RELEASE));
#else
  assert(!munmap(rx,65536));
#endif
  puts("pre-finalize corner install: inaccessible RX, bounded RW checks passed");return 0;
}
