#ifndef PES_STADIUM_ATMOSPHERE_H
#define PES_STADIUM_ATMOSPHERE_H
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "stadium_atmosphere_glsl.h"
#include "stadium_shell_clip.h"
static int stadium_atmosphere_scope(const char *source) {
  const char *body=strstr(source,"void main()");
  if(!body || !strstr(source,"#version 310 es"))return 0;
  if(stadium_shell_clip_scope(body))return 1;
  static const uint64_t known[]={
#include "stadium_atmosphere_fingerprints.inc"
  };
  const uint64_t hash=stadium_shell_clip_hash(body);
  for(unsigned i=0;i<sizeof(known)/sizeof(known[0]);++i)
    if(hash==known[i])return 1;
  return 0;
}
/* Admission is computed on the untouched, fingerprinted source before the
 * shell's alpha/clip reorder. Those existing edits remain byte-for-byte. */
static char *stadium_atmosphere_source(const char *source,int admitted) {
  if(!admitted || strstr(source,"nxRainMist") ||
      !strstr(source,"in highp vec4 in_TEXCOORD8;") ||
      !strstr(source,"View_WorldCameraOrigin") ||
      !strstr(source,"View_PreViewTranslation"))return NULL;
  const char *body=strstr(source,"void main()");
  const char *output=body ? strstr(body,"out_Target0.xyzw = ") : NULL;
  if(!output || strstr(output+1,"out_Target0.xyzw = "))return NULL;
  const char *end=strchr(output,';');if(!end)return NULL;
  ++end;
  static const char edit[]="\n\tout_Target0.xyz=nxRainMist(out_Target0.xyz,in_TEXCOORD8.xyz-View_PreViewTranslation,View_WorldCameraOrigin);\n";
  size_t before=(size_t)(body-source),middle=(size_t)(end-body),used=0;
  char *out=malloc(strlen(source)+sizeof(stadium_atmosphere_glsl)+sizeof(edit)+1);
  if(!out)return NULL;
  memcpy(out,source,before);used+=before;
  memcpy(out+used,stadium_atmosphere_glsl,sizeof(stadium_atmosphere_glsl)-1);used+=sizeof(stadium_atmosphere_glsl)-1;
  memcpy(out+used,body,middle);used+=middle;
  memcpy(out+used,edit,sizeof(edit)-1);used+=sizeof(edit)-1;
  strcpy(out+used,end);return out;
}
#endif
