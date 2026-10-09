#ifndef PES_NIGHT_LIGHTING_POLICY_H
#define PES_NIGHT_LIGHTING_POLICY_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Audited v5.3.0 perimeter/people/face/body fragment main fingerprints.
 * No cooked shader payloads are embedded. Unknown sources pass unchanged.
 * This is a scoped lighting compensation for the fallback High renderer,
 * not a correction to diffuse textures or the accepted Day pitch palette. */
static int night_lighting_body(const char *body) {
  static const uint32_t allowed[] = {
    0x0081d764u,0x02c83eccu,0x0872ed52u,0x089c1a64u,0x08de5b55u,
    0x0ba9a016u,0x0d107360u,0x0e57db47u,0x0fe30180u,0x112a6985u,
    0x1312c400u,0x1ac84851u,0x1b2284b7u,0x1b65f29eu,0x1b9585e4u,
    0x1be7620au,0x1d0f7902u,0x1db0ff6bu,0x1ffa8a0du,0x20f8a613u,
    0x2250cea8u,0x226b5adfu,0x2333229bu,0x240fe5fdu,0x24145763u,
    0x24766224u,0x27e7694cu,0x2833d53eu,0x297322c5u,0x2a554d0cu,
    0x2c78faeau,0x3a3b163cu,0x3ebcce2eu,0x4badde5fu,0x4cd29ca3u,
    0x4d3e733fu,0x4f22c7a1u,0x503f4531u,0x55f91d55u,0x560fbf21u,
    0x561bba1du,0x571ab6e2u,0x5a682f15u,0x5dd9636au,0x5f301a33u,
    0x689b8dc1u,0x69c3fa07u,0x6d780338u,0x6e690007u,0x7027971fu,
    0x72f9765du,0x73f18ce2u,0x78861f21u,0x79a18a0du,0x79b341acu,
    0x7a82b79fu,0x7be26165u,0x7dc24e54u,0x7f485828u,0x7fac8d5cu,
    0x80361abau,0x82547c5au,0x8418c5e5u,0x8b0911c6u,0x8d0d71adu,
    0x93cdb2ebu,0x97e97fc0u,0x9d25209bu,0x9ede0793u,0xa496cf8bu,
    0xa6f4020eu,0xa99dba55u,0xaac64a78u,0xab7dda00u,0xad0cd5c2u,
    0xae7ce389u,0xb0273e45u,0xb0c8f6efu,0xb61a4d61u,0xb876490au,
    0xb8843f35u,0xb9355a0du,0xbb9b91bbu,0xbd93eb0du,0xbfa19b83u,
    0xc13d6a29u,0xc1d21b6fu,0xc6d1b578u,0xc7b4caf5u,0xcb57d285u,
    0xcbb674a3u,0xd168e77au,0xd3488dc3u,0xd62bdc95u,0xdc9ad8c7u,
    0xe44a91cdu,0xe452a0bbu,0xe5a26a99u,0xe93fd577u,0xe94456d8u,
    0xedc5a146u,0xeef2c5ceu,0xeefff86fu,0xefe0424bu,0xf52da01au,
    0xf6f5a785u
  };
  uint32_t hash=2166136261u;
  for (const unsigned char *p=(const unsigned char *)body;*p;++p) {
    if (*p==' ' || *p=='\r' || *p=='\n' || *p=='\t') continue;
    hash=(hash^*p)*16777619u;
  }
  for (unsigned i=0;i<sizeof(allowed)/sizeof(allowed[0]);++i)
    if (hash==allowed[i]) return 1;
  return 0;
}

typedef struct { const char *end; char variable[16]; } NightLightingSite;

static int night_lighting_site(const char *body,const char *at,
                               NightLightingSite *site) {
  const char *line=at;
  while (line>body && line[-1]!='\n') --line;
  const char *end=strchr(at,';');
  if (!end || sscanf(line," %15[v0123456789].",site->variable)!=1 ||
      site->variable[0]!='v' || !site->variable[1]) return 0;
  site->end=end+1;
  return 1;
}

static char *night_lighting_source(const char *source) {
  const char *body=strstr(source,"void main()");
  if (!body || !night_lighting_body(body) || strstr(source,"nxNightIndirect")) return NULL;
  NightLightingSite sites[3]; unsigned count=0;

  /* Balance reconstructed SH irradiance, NOT its signed coefficients or the
   * resulting albedo. Geometry, shadow comparisons and light direction stay. */
  const char *indirect=strstr(body,"IndirectLightingCache_IndirectLightingSHCoefficients2.z;");
  if (indirect) {
    const char *positive=strstr(indirect,".xyz = max(vec3(0.000000e+00,0.000000e+00,0.000000e+00),");
    if (!positive || positive-indirect>512 || !night_lighting_site(body,positive,&sites[count])) return NULL;
    ++count;
  }
  const char *sky=strstr(body,".z = dot(View_SkyIrradianceEnvironmentMap[2],");
  if (sky) {
    if (strstr(sky+1,".z = dot(View_SkyIrradianceEnvironmentMap[2],") ||
        !night_lighting_site(body,sky,&sites[count])) return NULL;
    ++count;
  }

  /* Restore the v5 scope and cubemap insertion used by the better on-device
   * baseline. The v6 decoded/lightmap expansion regressed perimeter lighting.
   * Keep reflection-only bodies and baked lightmaps outside this candidate. */
  if (!count) return NULL;
  const char *cube=strstr(source,"samplerCube ");
  if (cube && cube<body) {
    char sampler[16]={0},token[40];
    if (sscanf(cube,"samplerCube %15[ps0123456789];",sampler)!=1) return NULL;
    snprintf(token,sizeof(token),"textureLod(%s,",sampler);
    const char *sample=strstr(body,token);
    if (sample) {
      if (strstr(sample+1,token) || !night_lighting_site(body,sample,&sites[count])) return NULL;
      ++count;
    }
  }
  if (!count) return NULL;
  for (unsigned i=0;i<count;++i)
    for (unsigned j=i+1;j<count;++j)
      if (sites[j].end<sites[i].end) {
        NightLightingSite swap=sites[i];sites[i]=sites[j];sites[j]=swap;
      }
  for (unsigned i=1;i<count;++i) if (sites[i].end==sites[i-1].end) return NULL;

  static const char helper[]=
    "uniform highp float nxNightIndirect;\n"
    "highp vec3 nxNightLight(highp vec3 light) {\n"
    "  if (nxNightIndirect > 0.5)\n"
    "    light.g = min(light.g, max(0.0, max(light.r, light.b)) * 1.05);\n"
    "  return light;\n"
    "}\n";
  const size_t n=strlen(source);
  char *result=malloc(n+sizeof(helper)+count*96u+1u);
  if (!result) return NULL;
  size_t used=(size_t)(body-source);
  memcpy(result,source,used);
  memcpy(result+used,helper,sizeof(helper)-1u);used+=sizeof(helper)-1u;
  const char *from=body;
  for (unsigned i=0;i<count;++i) {
    size_t length=(size_t)(sites[i].end-from);
    memcpy(result+used,from,length);used+=length;
    used+=(size_t)sprintf(result+used,"\n\t%s.xyz = nxNightLight(%s.xyz);",
                          sites[i].variable,sites[i].variable);
    from=sites[i].end;
  }
  strcpy(result+used,from);
  return result;
}
#endif
