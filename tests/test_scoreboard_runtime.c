#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>
static uint32_t exhibition_home_team_id=1,exhibition_away_team_id=2,key=9;
static uint32_t competition_frontend_scoreboard(uint32_t h,uint32_t a){assert(h==1&&a==2);return key;}
static void scene_runtime_note(const char *a,const char *b){(void)a;(void)b;}
#define PESNX_SCOREBOARD_HOST_TEST
#include "../source/scoreboard_runtime.inc"
static unsigned char copied[512];static unsigned calls;
static int expand(void *resource){
 unsigned char *p;uint32_t n;memcpy(&p,(char*)resource+0x18,8);memcpy(&n,(char*)resource+0x20,4);
 assert(n<=sizeof(copied));memcpy(copied,p,n);++calls;return 17;
}
static void u32(unsigned char *p,uint32_t v){for(int i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static void u64(unsigned char *p,uint64_t v){for(int i=0;i<8;i++)p[i]=(unsigned char)(v>>(8*i));}
int main(void){
 unsigned char original[128]={0},packet[160]={0},resource[64]={0};
 memcpy(original,"TXP2",4);original[15]=128;
 memcpy(packet,"NXSB01\0",8);u32(packet+8,128);u32(packet+12,128);
 memcpy(packet+32,original,128);packet[159]=99;
 u64(packet+16,nx_asset_hash(original,128));u64(packet+24,nx_asset_hash(packet+32,128));
 uint32_t size=0;assert(scoreboard_payload(packet,160,original,128,&size)==packet+32&&size==128);
 for(size_t n=0;n<160;n++)assert(!scoreboard_payload(packet,n,original,128,&size));
 packet[159]^=1;assert(!scoreboard_payload(packet,160,original,128,&size));packet[159]^=1;
 original[30]=1;assert(!scoreboard_payload(packet,160,original,128,&size));original[30]=0;
#ifdef _WIN32
 mkdir("Scoreboards");
#else
 mkdir("Scoreboards",0700);
#endif
 FILE *f=fopen("Scoreboards/c9.nxsb","wb");assert(f);assert(fwrite(packet,1,160,f)==160);fclose(f);
 resource[0]=18;memcpy(resource+1,"game2dPes",10);
 unsigned char *p=original;memcpy(resource+0x18,&p,8);u32(resource+0x20,128);
 unsigned char before[64];memcpy(before,resource,64);scoreboard_expand_original=expand;
 for(int match=0;match<100;match++){
   key=match%2?9:0;assert(scoreboard_expand(resource)==17);
   assert(!memcmp(resource,before,64));assert(original[127]==0);
   assert(copied[127]==(key?99:0));
 }
 key=27;assert(scoreboard_expand(resource)==17&&copied[127]==0); /* absent theme */
 assert(calls==101);
 /* The common banner can replace the native resource without a league theme.
  * Both selected and fallback packets still require the full source binding. */
 packet[159]=66;u64(packet+24,nx_asset_hash(packet+32,128));
 f=fopen("Scoreboards/c0.nxsb","wb");assert(f);assert(fwrite(packet,1,160,f)==160);fclose(f);
 key=0;assert(scoreboard_expand(resource)==17&&copied[127]==66);
 key=27;assert(scoreboard_expand(resource)==17&&copied[127]==66);
 key=9;assert(scoreboard_expand(resource)==17&&copied[127]==99);
 packet[159]^=1; /* Deliberately malformed selected packet. */
 f=fopen("Scoreboards/c9.nxsb","wb");assert(f);assert(fwrite(packet,1,160,f)==160);fclose(f);
 assert(scoreboard_expand(resource)==17&&copied[127]==66);
 original[30]=1;assert(scoreboard_expand(resource)==17&&copied[127]==0);original[30]=0;
 assert(!memcmp(resource,before,64));
 assert(remove("Scoreboards/c0.nxsb")==0);
 assert(scoreboard_expand(resource)==17&&copied[127]==0);
 packet[159]=55;u64(packet+24,nx_asset_hash(packet+32,128));
 f=fopen("Scoreboards/banner-textures.nxsb","wb");assert(f);assert(fwrite(packet,1,160,f)==160);fclose(f);
 memset(resource+1,0,23);memcpy(resource+1,"licenceTexturePes",18);
 assert(scoreboard_expand(resource)==17&&copied[127]==55);
 const char *native_name="afp_licenceTexturePes.apk";
 resource[0]=1;memcpy(resource+0x10,&native_name,sizeof(native_name));
 assert(scoreboard_expand(resource)==17&&copied[127]==55);
 assert(remove("Scoreboards/banner-textures.nxsb")==0);
 assert(scoreboard_expand(resource)==17&&copied[127]==0);
 assert(calls==110);puts("scoreboard temporary ownership, malformed input and repeated-theme fallback passed");
}
