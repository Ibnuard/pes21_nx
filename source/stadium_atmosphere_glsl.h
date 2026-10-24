#ifndef PES_STADIUM_ATMOSPHERE_GLSL_H
#define PES_STADIUM_ATMOSPHERE_GLSL_H
/* Scene radiance, before native tonemapping. No screen overlay or alpha edit.
 * Simpson's three height samples approximate density along the viewing ray;
 * distant raised stands remain in the same atmosphere as the pitch. */
static const char stadium_atmosphere_glsl[] =
  "uniform highp float nxDayStadium;\n"
  "uniform highp vec4 nxStadiumClimate;\n"
  "highp float nxAirDensity(highp float height) {\n"
  "  return 1.0/(1.0+max(height,0.0)/6000.0);\n"
  "}\n"
  "highp vec3 nxRainMist(highp vec3 color,highp vec3 world,highp vec3 camera) {\n"
  "  if(nxStadiumClimate.x<1.5) return color;\n"
  "  highp vec3 ray=world-camera;\n"
  "  highp float density=(nxAirDensity(camera.z)+4.0*nxAirDensity((camera.z+world.z)*0.5)+nxAirDensity(world.z))/6.0;\n"
  "  highp float day=step(0.5,nxDayStadium);\n"
  "  highp float winter=step(0.5,nxStadiumClimate.y);\n"
  "  highp float optical=length(ray)*mix(0.000035,0.000055,day)*density;\n"
  "  optical*=mix(1.0,0.35,winter);\n"
  "  highp float amount=min(mix(mix(0.32,0.42,day),mix(0.12,0.18,day),winter),optical/(1.0+optical));\n"
  "  highp vec3 haze=mix(vec3(0.09,0.10,0.12),vec3(0.34,0.37,0.40),day);\n"
  "  haze=mix(haze,mix(vec3(0.12,0.14,0.17),vec3(0.44,0.48,0.53),day),winter);\n"
  "  return mix(color,haze,amount);\n"
  "}\n";
#endif
