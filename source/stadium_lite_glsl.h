#ifndef PES_STADIUM_LITE_GLSL_H
#define PES_STADIUM_LITE_GLSL_H

/* Authored analytic roof proxy, in UE centimetres. It is shared by pitch,
 * bodies and faces: moving receivers intersect the same elevated plane.
 * No native roof mesh, depth atlas, texture binding or extra draw is needed.
 * Keep helpers as separate strings so host tests can execute the exact math. */
static const char stadium_lite_geometry_glsl[] =
  "highp float nxRoofDistance(highp vec2 p, highp vec2 extent, highp float radius) {\n"
  "  highp vec2 q=abs(p)-extent+vec2(radius);\n"
  "  return length(max(q,vec2(0.0)))+min(max(q.x,q.y),0.0)-radius;\n"
  "}\n"
  "highp float nxRoofProxy(highp vec2 p, highp float edge) {\n"
  "  highp float inner=nxRoofDistance(p,vec2(5700.0,3700.0),1400.0);\n"
  "  highp float outer=nxRoofDistance(p,vec2(7800.0,5800.0),2000.0);\n"
  "  highp float roof=smoothstep(-edge,edge,inner)*(1.0-smoothstep(-edge,edge,outer));\n"
  "  highp float slot1=smoothstep(260.0-edge,260.0+edge,inner)*(1.0-smoothstep(620.0-edge,620.0+edge,inner));\n"
  "  highp float slot2=smoothstep(1050.0-edge,1050.0+edge,inner)*(1.0-smoothstep(1360.0-edge,1360.0+edge,inner));\n"
  "  highp vec2 side=abs(p)-vec2(4300.0,2300.0);\n"
  "  highp float along=(side.x>side.y)?p.y:p.x;\n"
  "  highp float beam=abs(fract(along/650.0+0.5)-0.5)*650.0;\n"
  "  highp float opening=max(slot1,slot2)*smoothstep(24.0-edge,24.0+edge,beam);\n"
  "  return 1.0-roof*(1.0-opening);\n"
  "}\n"
  "highp vec2 nxRoofProject(highp vec3 world,highp vec3 light) {\n"
  "  return world.xy+light.xy*((3600.0-world.z)/max(light.z,0.2));\n"
  "}\n";

static const char stadium_lite_helpers_glsl[] =
  "uniform highp float nxNightIndirect;\n"
  "uniform highp float nxDayStadium;\n"
  "highp vec3 nxNeutralLight(highp vec3 light) {\n"
  "  if(nxNightIndirect>0.5 || nxDayStadium>0.5)\n"
  "    return vec3(dot(max(light,vec3(0.0)),vec3(0.2126,0.7152,0.0722)));\n"
  "  return light;\n"
  "}\n"
  "highp float nxRoofVisibility(highp vec3 world) {\n"
  "  highp vec2 p=nxRoofProject(world,MobileDirectionalLight_DirectionalLightDirectionAndShadowTransition.xyz);\n"
  "  highp float edge=clamp(max(fwidth(p.x),fwidth(p.y))*0.75,8.0,70.0);\n"
  "  return nxRoofProxy(p,edge);\n"
  "}\n"
  "highp vec3 nxDirectLight(highp vec3 light,highp float visibility) {\n"
  "  return nxNeutralLight(light)*mix(0.12,1.0,visibility);\n"
  "}\n"
  "highp vec3 nxAmbientLight(highp vec3 light,highp float visibility) {\n"
  "  return nxNeutralLight(light)*mix(0.56,1.0,visibility);\n"
  "}\n"
  "highp vec3 nxPitchGrain(highp vec3 albedo,highp float grain) {\n"
  "  if(nxDayStadium>0.5 && albedo.g>albedo.r*1.14 && albedo.g>albedo.b*1.3)\n"
  "    return (albedo*vec3(0.82,1.18,0.74))*mix(0.84,1.16,clamp(grain,0.0,1.0));\n"
  "  return albedo;\n"
  "}\n"
  "highp vec3 nxPitchSheen(highp vec3 light,highp float visibility) {\n"
  "  if(nxDayStadium>0.5) return nxNeutralLight(light)*(0.06*visibility);\n"
  "  return light;\n"
  "}\n";
#endif
