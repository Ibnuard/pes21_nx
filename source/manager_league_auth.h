#ifndef PESNX_MANAGER_LEAGUE_AUTH_H
#define PESNX_MANAGER_LEAGUE_AUTH_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Local prototype credentials only. Server authentication and global account
 * uniqueness require a backend. No PIN/password or reusable session persists.
 * v1 is read only for one-time password verification; v2 creates PIN gates. */
enum { MD_AUTH_ROUNDS=120000 };
typedef struct {
  uint32_t magic,version,bytes,rounds,seed,checksum;
  char user_id[32];
  uint8_t salt[16],verifier[32];
} MdCredential;
typedef struct {uint32_t h[8];uint64_t bytes;uint8_t block[64];uint32_t used;} MdSha;
static inline void md_auth_wipe(void *p,size_t bytes) {
  volatile uint8_t *b=p;while(bytes--)*b++=0;
}
static inline uint32_t md_sha_rotr(uint32_t x,uint32_t n){return (x>>n)|(x<<(32-n));}
static inline void md_sha_block(MdSha *c,const uint8_t *b) {
  static const uint32_t k[64]={
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
  uint32_t w[64];for(uint32_t i=0;i<16;i++)w[i]=(uint32_t)b[i*4]<<24|(uint32_t)b[i*4+1]<<16|(uint32_t)b[i*4+2]<<8|b[i*4+3];
  for(uint32_t i=16;i<64;i++) {
    uint32_t a=w[i-15],z=w[i-2];
    w[i]=w[i-16]+(md_sha_rotr(a,7)^md_sha_rotr(a,18)^(a>>3))+w[i-7]+(md_sha_rotr(z,17)^md_sha_rotr(z,19)^(z>>10));
  }
  uint32_t a=c->h[0],d=c->h[3],e=c->h[4],h=c->h[7],bb=c->h[1],cc=c->h[2],f=c->h[5],g=c->h[6];
  for(uint32_t i=0;i<64;i++) {
    uint32_t t=h+(md_sha_rotr(e,6)^md_sha_rotr(e,11)^md_sha_rotr(e,25))+((e&f)^(~e&g))+k[i]+w[i];
    uint32_t u=(md_sha_rotr(a,2)^md_sha_rotr(a,13)^md_sha_rotr(a,22))+((a&bb)^(a&cc)^(bb&cc));
    h=g;g=f;f=e;e=d+t;d=cc;cc=bb;bb=a;a=t+u;
  }
  c->h[0]+=a;c->h[1]+=bb;c->h[2]+=cc;c->h[3]+=d;c->h[4]+=e;c->h[5]+=f;c->h[6]+=g;c->h[7]+=h;
  md_auth_wipe(w,sizeof(w));
}
static inline MdSha md_sha_init(void) {
  return (MdSha){{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19},0,{0},0};
}
static inline void md_sha_update(MdSha *c,const void *input,size_t bytes) {
  const uint8_t *b=input;c->bytes+=bytes;
  while(bytes){size_t take=64-c->used;if(take>bytes)take=bytes;memcpy(c->block+c->used,b,take);c->used+=(uint32_t)take;b+=take;bytes-=take;
    if(c->used==64){md_sha_block(c,c->block);c->used=0;}}
}
static inline void md_sha_final(MdSha *c,uint8_t out[32]) {
  uint64_t bits=c->bytes*8;c->block[c->used++]=128;
  if(c->used>56){memset(c->block+c->used,0,64-c->used);md_sha_block(c,c->block);c->used=0;}
  memset(c->block+c->used,0,56-c->used);for(uint32_t i=0;i<8;i++)c->block[63-i]=(uint8_t)(bits>>(i*8));md_sha_block(c,c->block);
  for(uint32_t i=0;i<32;i++)
    out[i]=(uint8_t)(c->h[i/4]>>(24-(i%4)*8));
  md_auth_wipe(c,sizeof(*c));
}
static inline void md_auth_kdf(const char *password,const uint8_t salt[16],uint32_t rounds,uint8_t out[32]) {
  MdSha in=md_sha_init(),outer=md_sha_init();uint8_t pad[64],u[32],key[32],first[20];size_t n=strlen(password);
  const uint8_t *p=(const uint8_t *)password;
  if(n>64){MdSha c=md_sha_init();md_sha_update(&c,p,n);md_sha_final(&c,key);p=key;n=32;}
  memset(pad,0x36,64);for(size_t i=0;i<n;i++)pad[i]^=p[i];md_sha_update(&in,pad,64);
  memset(pad,0x5c,64);for(size_t i=0;i<n;i++)pad[i]^=p[i];md_sha_update(&outer,pad,64);
  memcpy(first,salt,16);first[16]=first[17]=first[18]=0;first[19]=1;
  memset(out,0,32);
  for(uint32_t r=0;r<rounds;r++) {
    MdSha c=in;md_sha_update(&c,r ? (const void *)u : (const void *)first,r ? 32 : 20);md_sha_final(&c,u);
    c=outer;md_sha_update(&c,u,32);md_sha_final(&c,u);for(uint32_t i=0;i<32;i++)out[i]^=u[i];
  }
  md_auth_wipe(&in,sizeof(in));md_auth_wipe(&outer,sizeof(outer));md_auth_wipe(pad,sizeof(pad));md_auth_wipe(u,32);md_auth_wipe(key,32);md_auth_wipe(first,20);
}
static inline int md_auth_id(char out[32],const char *id) {
  size_t n=strlen(id);if(n<3 || n>24)return 0;memset(out,0,32);
  for(size_t i=0;i<n;i++) {
    char ch=id[i];if(ch>='A'&&ch<='Z')ch+=(char)('a'-'A');
    if(!((ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||ch=='.'||ch=='_'))return 0;
    out[i]=ch;
  }
  return 1;
}
static inline uint32_t md_auth_checksum(const MdCredential *p) {
  MdCredential c=*p;c.checksum=0;const uint8_t *b=(const uint8_t *)&c;uint32_t h=2166136261u;
  for(size_t i=0;i<sizeof(c);i++)
    h=(h^b[i])*16777619u;
  md_auth_wipe(&c,sizeof(c));return h;
}
static inline int md_auth_valid(const MdCredential *p,uint32_t seed,const char *id) {
  char canonical[32];return md_auth_id(canonical,id) && p->magic==0x4d4c4131u && (p->version==1 || p->version==2) && p->bytes==sizeof(*p) &&
    p->rounds==MD_AUTH_ROUNDS && p->seed==seed && !memcmp(canonical,p->user_id,32) && p->checksum==md_auth_checksum(p);
}
static inline int md_auth_pin_valid(const char *pin) {
  if(!pin || strlen(pin)!=4)return 0;
  for(uint32_t i=0;i<4;i++)if(pin[i]<'0' || pin[i]>'9')return 0;
  return 1;
}
static inline int md_auth_create(MdCredential *p,uint32_t seed,const char *id,const char *pin,const uint8_t salt[16]) {
  if(!md_auth_pin_valid(pin))return 0;
  memset(p,0,sizeof(*p));
  if(!md_auth_id(p->user_id,id))return 0;
  p->magic=0x4d4c4131u;p->version=2;p->bytes=sizeof(*p);p->rounds=MD_AUTH_ROUNDS;p->seed=seed;memcpy(p->salt,salt,16);
  md_auth_kdf(pin,salt,p->rounds,p->verifier);p->checksum=md_auth_checksum(p);return 1;
}
static inline int md_auth_verify(const MdCredential *p,uint32_t seed,const char *id,const char *password) {
  if(!md_auth_valid(p,seed,id) || (p->version==2 ? !md_auth_pin_valid(password) : (strlen(password)<8 || strlen(password)>63)))return 0;
  uint8_t hash[32],different=0;md_auth_kdf(password,p->salt,p->rounds,hash);
  for(uint32_t i=0;i<32;i++)
    different|=hash[i]^p->verifier[i];
  md_auth_wipe(hash,32);return !different;
}
#endif
