/* Replace the native score atlas at its synchronous ownership boundary.
 * Scripts/bindings remain native; temporary input is freed only after the
 * AfpBin package has copied/expanded it into its own allocation. */
#include "runtime_assets.h"
static int (*scoreboard_expand_original)(void *);
static uint32_t scoreboard_be32(const unsigned char *p) {
  return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static unsigned char *scoreboard_payload(unsigned char *file,size_t bytes,
    const unsigned char *original,size_t original_bytes,uint32_t *size) {
  if (!file || bytes<32+108 || !original || original_bytes<108 ||
      memcmp(file,"NXSB01\0",8) || memcmp(original,"TXP2",4)) return NULL;
  const uint32_t source_size=nx_asset_u32(file+8), target_size=nx_asset_u32(file+12);
  if (source_size<108 || source_size>original_bytes || target_size!=bytes-32 ||
      source_size!=scoreboard_be32(original+12) || memcmp(file+32,"TXP2",4) ||
      scoreboard_be32(file+44)!=target_size ||
      nx_asset_hash(original,source_size)!=nx_asset_u64(file+16) ||
      nx_asset_hash(file+32,target_size)!=nx_asset_u64(file+24)) return NULL;
  *size=target_size;
  return file+32;
}
static int scoreboard_expand(void *resource) {
  if (!resource) return scoreboard_expand_original(resource);
  unsigned char *r=resource;
  const char *name=(const char *)r+1;
  if (r[0]&1) memcpy(&name,r+0x10,sizeof(name));
  if (!name || strnlen(name,256)==256 || !strstr(name,"game2dPes"))
    return scoreboard_expand_original(resource);
  uint32_t key=competition_frontend_scoreboard(
      __atomic_load_n(&exhibition_home_team_id,__ATOMIC_ACQUIRE),
      __atomic_load_n(&exhibition_away_team_id,__ATOMIC_ACQUIRE));
  if (!key) return scoreboard_expand_original(resource);
  unsigned char *original;
  uint32_t old_size;
  memcpy(&original,r+0x18,sizeof(original));
  memcpy(&old_size,r+0x20,4);
  char path[64];
  snprintf(path,sizeof(path),"Scoreboards/c%u.nxsb",key);
  size_t bytes=0;
  unsigned char *file=nx_asset_read(path,2000000,&bytes);
  uint32_t new_size=0;
  unsigned char *replacement=scoreboard_payload(file,bytes,original,old_size,&new_size);
  if (!replacement) {
    free(file);
    scene_runtime_note("scoreboard","theme absent/incompatible; native UI retained");
    return scoreboard_expand_original(resource);
  }
  memcpy(r+0x18,&replacement,sizeof(replacement));
  memcpy(r+0x20,&new_size,4);
  const int result=scoreboard_expand_original(resource);
  memcpy(r+0x18,&original,sizeof(original));
  memcpy(r+0x20,&old_size,4);
  free(file);
  scene_runtime_note("scoreboard",path);
  return result;
}
#ifndef PESNX_SCOREBOARD_HOST_TEST
static void install_scoreboard_runtime(so_module *module) {
  const uintptr_t plt=(uintptr_t)module->load_base+0x38e71e0;
  const uint32_t words[]={0xd002e250,0xf945a611,0x912d2210,0xd61f0220};
  if (memcmp((void *)plt,words,16)) return;
  scoreboard_expand_original=(void *)so_try_find_addr_rx(module,
      "_ZN5flash7Package6AfpBin8Resource12ExpandedDataEv");
  if (!scoreboard_expand_original) return;
  hook_arm64(plt,(uintptr_t)scoreboard_expand);
}
#endif
