#ifndef PES_STADIUM_LIGHTING_POLICY_H
#define PES_STADIUM_LIGHTING_POLICY_H
#include "night_lighting_policy.h"
#include "stadium_lite_glsl.h"

/* Audited character/perimeter and Day pitch shaders only. Shared material
 * hashes never authorize skin/kit recolouring. All changes have runtime gates;
 * Night pitch and unknown shaders are outside this policy. */
static unsigned stadium_lighting_scope(const char *body) {
  static const struct { uint32_t hash; unsigned scope; } known[] = {
#include "stadium_lighting_fingerprints.inc"
    {0x038325c5u,8},{0x284db1fau,8},{0x2ba923ebu,8},{0x2d9e5957u,8},
    {0x37966a69u,8},{0x3e3879b5u,8},{0x523e5f8cu,8},{0x536331a8u,8},
    {0x713d2026u,8},{0x7e2c0da5u,8},{0x97e96ba6u,8},{0x9e0b3576u,8},
    {0xa251829cu,8},{0xb51dd7c1u,8},{0xbd0af1c0u,8},{0xbe93c4b6u,8},
    {0xefff8d62u,8},{0xf0d87d2du,8},
  };
  uint32_t hash=2166136261u;
  for(const unsigned char *p=(const unsigned char *)body;*p;++p) {
    if(*p==' ' || *p=='\r' || *p=='\n' || *p=='\t')continue;
    hash=(hash^*p)*16777619u;
  }
  for(unsigned i=0;i<sizeof(known)/sizeof(known[0]);++i)
    if(known[i].hash==hash)return known[i].scope;
  return 0;
}

typedef struct { const char *at; size_t length; char text[768]; } StadiumLightEdit;
static int stadium_light_after(const char *body,const char *at,
    StadiumLightEdit *edit,const char *function) {
  NightLightingSite site;
  if(!night_lighting_site(body,at,&site))return 0;
  edit->at=site.end;edit->length=0;
  snprintf(edit->text,sizeof(edit->text),"\n\t%s.xyz = %s(%s.xyz%s);",
           site.variable,function,site.variable,
           !strcmp(function,"nxAmbientLight") ? ",nxRoofLight" : "");
  return 1;
}

static char *stadium_lighting_source(const char *source) {
  const char *body=strstr(source,"void main()");
  const unsigned scope=body ? stadium_lighting_scope(body) : 0;
  if(!scope || strstr(source,"nxNightIndirect"))return NULL;
  if(!strstr(source,"in highp vec4 in_TEXCOORD8;") ||
     !strstr(source,"View_PreViewTranslation"))return NULL;
  StadiumLightEdit edits[32];unsigned count=0;
  const char *begin=strchr(body,'{');if(!begin)return NULL;
  edits[count].at=begin+1;edits[count].length=0;
  strcpy(edits[count++].text,"\n\thighp float nxRoofLight=1.0;\n"
      "\tif(nxDayStadium>0.5) nxRoofLight=nxRoofVisibility(in_TEXCOORD8.xyz-View_PreViewTranslation);\n");
  const char *sh=strstr(body,"IndirectLightingCache_IndirectLightingSHCoefficients2.z;");
  if(sh) {
    const char *positive=strstr(sh,".xyz = max(vec3(0.000000e+00,0.000000e+00,0.000000e+00),");
    /* Pitch multiplies SH by albedo in the following assignment. Correct
     * the reconstructed irradiance BEFORE that multiplication. */
    if(scope&8u)positive=strstr(sh,".z = (");
    if(!positive || positive-sh>512 ||
       !stadium_light_after(body,positive,&edits[count++],"nxNeutralLight"))return NULL;
  }
  const char *sky=strstr(body,".z = dot(View_SkyIrradianceEnvironmentMap[2],");
  if(sky && !stadium_light_after(body,sky,&edits[count++],"nxAmbientLight"))return NULL;
  const char *baked=strstr(body,"+PrecomputedLightingBuffer_LightMapAdd[1]");
  if(baked) {
    const char *decoded=strstr(baked,"*vec3((");
    if(!decoded || decoded-baked>512 ||
       !stadium_light_after(body,decoded,&edits[count++],"nxNeutralLight"))return NULL;
  }
  /* Operate on decoded radiance in BOTH cube branches. RGBM encoding and
   * signed SH coefficients are never colour corrected. */
  const char *cube=strstr(source,"samplerCube ");
  if(cube && cube<body) {
    char sampler[16],token[48];
    if(sscanf(cube,"samplerCube %15[ps0123456789];",sampler)!=1)return NULL;
    snprintf(token,sizeof(token),"textureLod(%s,",sampler);
    const char *sample=strstr(body,token);
    if(!sample)return NULL;
    const char *otherwise=strstr(sample,"\n\telse\n");
    const char *close=otherwise ? strstr(otherwise,"\n\t}") : NULL;
    if(!close || close-sample>1024)return NULL;
    const char *decoded=close;
    while(decoded>otherwise && (decoded[-1]=='\r' || decoded[-1]=='\n' ||
          decoded[-1]==' ' || decoded[-1]=='\t'))--decoded;
    if(decoded<=otherwise || decoded[-1]!=';')return NULL;
    NightLightingSite site;
    if(!night_lighting_site(body,decoded-1,&site))return NULL;
    edits[count].at=close+3;edits[count].length=0;
    snprintf(edits[count++].text,768,"\n\t%s.xyz = nxAmbientLight(%s.xyz,nxRoofLight);",site.variable,site.variable);
  }
  /* These tints are applied after SH/cube reconstruction; balancing only
   * the earlier sample lets a green skylight multiply the cast back in. */
  const char *colors[]={"MobileDirectionalLight_DirectionalLightColor.xyz",
      "View_SkyLightColor.xyz","View_IndirectLightingColorScale"};
  for(unsigned i=0;i<3;++i) {
    const char *at=body;
    while((at=strstr(at,colors[i]))!=NULL) {
      if(count>=24)return NULL;
      edits[count].at=at;edits[count].length=strlen(colors[i]);
      snprintf(edits[count++].text,768,"%s(%s%s)",
          i==0 ? "nxDirectLight" : i==2 ? "nxAmbientLight" : "nxNeutralLight",
          colors[i],i==1 ? "" : ",nxRoofLight");
      at+=strlen(colors[i]);
    }
  }
  /* Skip the costly nine depth fetches even if an old CSM permutation is
   * reused after switching matches. Native Night/Standard keep their PCF. */
  const char *pcf_tests[]={"if ((v2.z>0.000000e+00))","if ((v3.z>0.000000e+00))"};
  for(unsigned i=0;i<2;++i) {
    const char *pcf=strstr(body,pcf_tests[i]);
    if(!pcf)continue;
    edits[count].at=pcf;edits[count].length=strlen(pcf_tests[i]);
    snprintf(edits[count++].text,768,"if (nxDayStadium<0.5 && (v%u.z>0.000000e+00))",i+2);
  }
  if(scope&8u) {
    NightLightingSite detail,albedo,sheen,mask,tint;
    const char *d=strstr(body,".xyzw = texture(ps3,");
    const char *a=strstr(body,".xyz = ((texture(ps0,");
    const char *s=strstr(body,"vec3(8.755540e-01,1.000000e+00,0.000000e+00)");
    const char *m=strstr(body,".xyzw = texture(ps1,in_TEXCOORD0.zw);");
    const char *t=strstr(body,"+(Material_VectorExpressions[1].xyz*");
    if(!d||!a||!s||!m||!t || !night_lighting_site(body,d,&detail) ||
        !night_lighting_site(body,a,&albedo) || !night_lighting_site(body,s,&sheen) ||
        !night_lighting_site(body,m,&mask) || !night_lighting_site(body,t,&tint))return NULL;
    edits[count].at=albedo.end;edits[count].length=0;
    snprintf(edits[count++].text,768,"\n\t%s.xyz = nxPitchGrain(%s.xyz,%s.w);",albedo.variable,albedo.variable,detail.variable);
    edits[count].at=sheen.end;edits[count].length=0;
    snprintf(edits[count++].text,768,"\n\t%s.xyz = nxPitchSheen(%s.xyz,nxRoofLight);",sheen.variable,sheen.variable);
    edits[count].at=mask.end;edits[count].length=0;
    snprintf(edits[count++].text,768,"\n\tif(nxDayStadium>0.5) %s.xyzw=vec4(1.0);",mask.variable);
    /* Remove only the two additive yellow material tints in the Day gate;
     * native paint/stripe samples, detail UVs and texture mips are retained. */
    const char *tline=t;while(tline>body && tline[-1]!='\n')--tline;
    char base[16];
    const char *clamp=strstr(tline,"clamp(((");
    if(!clamp || clamp>t || sscanf(clamp,"clamp(((%15[v0123456789]",base)!=1)return NULL;
    edits[count].at=tint.end;edits[count].length=0;
    snprintf(edits[count++].text,768,"\n\tif(nxDayStadium>0.5) %s.xyz=clamp(%s,vec3(0.0),vec3(1.0));",tint.variable,base);
  }
  if(!count)return NULL;
  for(unsigned i=0;i<count;++i)for(unsigned j=i+1;j<count;++j)
    if(edits[j].at<edits[i].at){StadiumLightEdit tmp=edits[i];edits[i]=edits[j];edits[j]=tmp;}
  for(unsigned i=1;i<count;++i)
    if(edits[i].at<edits[i-1].at+edits[i-1].length)return NULL;
  char *result=malloc(strlen(source)+sizeof(stadium_lite_geometry_glsl)+sizeof(stadium_lite_helpers_glsl)+count*768u+1u);
  if(!result)return NULL;
  size_t used=(size_t)(body-source);memcpy(result,source,used);
  memcpy(result+used,stadium_lite_geometry_glsl,sizeof(stadium_lite_geometry_glsl)-1);used+=sizeof(stadium_lite_geometry_glsl)-1;
  memcpy(result+used,stadium_lite_helpers_glsl,sizeof(stadium_lite_helpers_glsl)-1);used+=sizeof(stadium_lite_helpers_glsl)-1;
  const char *from=body;
  for(unsigned i=0;i<count;++i) {
    const size_t n=(size_t)(edits[i].at-from);memcpy(result+used,from,n);used+=n;
    const size_t add=strlen(edits[i].text);memcpy(result+used,edits[i].text,add);used+=add;
    from=edits[i].at+edits[i].length;
  }
  strcpy(result+used,from);return result;
}
#endif
