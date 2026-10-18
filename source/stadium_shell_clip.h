#ifndef PESNX_STADIUM_SHELL_CLIP_H
#define PESNX_STADIUM_SHELL_CLIP_H
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

/* Project-authored, cooked shell shaders only. Move the RGB fetch behind the
 * existing camera/alpha discard; preserve its exact gradients before discard.
 * No draw-time work, texture binding, light, or altered coverage is introduced. */
static inline uint64_t stadium_shell_clip_hash(const char *body) {
  uint64_t hash=UINT64_C(14695981039346656037);
  for(const unsigned char *p=(const unsigned char *)body;*p;++p) {
    if(*p==' ' || *p=='\r' || *p=='\n' || *p=='\t') continue;
    hash=(hash^*p)*UINT64_C(1099511628211);
  }
  return hash;
}
static inline int stadium_shell_clip_scope(const char *body) {
  static const uint64_t known[]={
    UINT64_C(0),
#include "stadium_shell_clip_fingerprints.inc"
  };
  const uint64_t hash=stadium_shell_clip_hash(body);
  for(unsigned i=1;i<sizeof(known)/sizeof(known[0]);++i)
    if(hash==known[i]) return 1;
  return 0;
}
static inline int stadium_shell_clip_identifier(const char *at,const char *name,size_t n) {
  return !strncmp(at,name,n) && !(isalnum((unsigned char)at[n]) || at[n]=='_');
}
static inline char *stadium_shell_clip_transform(const char *source) {
  if(!source) return NULL;
  if(!strstr(source,"#version 310 es") || strstr(source,"nxShellEarlyClip")) return NULL;
  const char *body=strstr(source,"void main()");
  if(!body || !strstr(body,"View_WorldCameraOrigin") ||
      !strstr(body,"vec3(-5.800000e+03,-4.000000e+03,-5.000000e+01)") ||
      !strstr(body,"vec3(5.800000e+03,4.000000e+03,2.600000e+02)")) return NULL;
  const char *sample=strstr(body,"textureGrad("),*implicit=strstr(body,"texture(");
  if(!sample || (implicit && implicit<sample)) sample=implicit;
  const char *discard=strstr(body,"discard;");
  if(!sample || !discard || sample>=discard) return NULL;
  for(const char *next=discard;(next=strstr(next+8,"discard;"))!=NULL;) discard=next;
  const char *discard_end=discard+8;
  const char *start=sample;
  while(start>body && start[-1]!='\n' && start[-1]!='\r') --start;
  const char *end=strchr(sample,';');
  if(!end || end>=discard) return NULL;
  ++end;
  const char *lhs=start;
  while(lhs<sample && isspace((unsigned char)*lhs)) ++lhs;
  size_t lhs_n=0;
  while(isalnum((unsigned char)lhs[lhs_n]) || lhs[lhs_n]=='_') ++lhs_n;
  if(!lhs_n || lhs_n>=48 || strncmp(lhs+lhs_n,".xyz = (",8)) return NULL;
  if(!strstr(sample,".xyz*in_COLOR0.xxx)")) return NULL;
  /* The saved colour must not be read by the coverage calculation. */
  char variable[48]; memcpy(variable,lhs,lhs_n); variable[lhs_n]=0;
  for(const char *p=end;p<discard_end;++p)
    if((p==end || !(isalnum((unsigned char)p[-1]) || p[-1]=='_')) &&
        stadium_shell_clip_identifier(p,variable,lhs_n)) return NULL;

  const int explicit_gradient=!strncmp(sample,"textureGrad(",12);
  const char *arg=sample+(explicit_gradient?12:8),*cursor=arg;
  char arguments[4][768]; unsigned count=0,depth=0;
  for(;;++cursor) {
    if(!*cursor || cursor>=end) return NULL;
    if(*cursor=='(') ++depth;
    else if(*cursor==')' && depth) --depth;
    else if((*cursor==',' || *cursor==')') && !depth) {
      size_t n=(size_t)(cursor-arg);
      if(count>=4 || !n || n>=sizeof(arguments[0])) return NULL;
      memcpy(arguments[count],arg,n); arguments[count++][n]=0;
      if(*cursor==')') break;
      arg=cursor+1;
    }
  }
  if(count!=(explicit_gradient?4u:2u)) return NULL;
  const char *sample_end=cursor+1;
  char gradients[1800],colour[3072]; int gn;
  if(explicit_gradient)
    gn=snprintf(gradients,sizeof(gradients),"\n\t/* nxShellEarlyClip v31 */\n\thighp vec2 nxShellColorDx=%s;\n\thighp vec2 nxShellColorDy=%s;\n",arguments[2],arguments[3]);
  else
    gn=snprintf(gradients,sizeof(gradients),"\n\t/* nxShellEarlyClip v31 */\n\thighp vec2 nxShellColorDx=dFdx(%s);\n\thighp vec2 nxShellColorDy=dFdy(%s);\n",arguments[1],arguments[1]);
  if(gn<0 || (size_t)gn>=sizeof(gradients)) return NULL;
  int cn=snprintf(colour,sizeof(colour),"\n%.*stextureGrad(%s,%s,nxShellColorDx,nxShellColorDy)%.*s\n",
      (int)(sample-start),start,arguments[0],arguments[1],(int)(end-sample_end),sample_end);
  if(cn<0 || (size_t)cn>=sizeof(colour)) return NULL;
  const size_t length=strlen(source),prefix=(size_t)(start-source);
  if(length>2u*1024u*1024u) return NULL;
  char *out=(char *)malloc(length+(size_t)gn+(size_t)cn+1);
  if(!out) return NULL;
  char *target=out;
#define NX_SHELL_COPY(at,n) do {size_t bytes=(size_t)(n);memcpy(target,(at),bytes);target+=bytes;} while(0)
  NX_SHELL_COPY(source,prefix);
  NX_SHELL_COPY(gradients,gn);
  NX_SHELL_COPY(end,discard_end-end);
  NX_SHELL_COPY(colour,cn);
  NX_SHELL_COPY(discard_end,length-(size_t)(discard_end-source));
#undef NX_SHELL_COPY
  *target=0;
  return out;
}
static inline char *stadium_shell_clip_source(const char *source) {
  if(!source) return NULL;
  const char *body=strstr(source,"void main()");
  if(!body || !strstr(source,"#version 310 es") ||
      !strstr(body,"vec3(-5.800000e+03,-4.000000e+03,-5.000000e+01)") ||
      !stadium_shell_clip_scope(body)) return NULL;
  return stadium_shell_clip_transform(source);
}
#endif
