#ifndef PESNX_STADIUM_ROOF_PROFILES_H
#define PESNX_STADIUM_ROOF_PROFILES_H
#include <string.h>
/* Offline measured analytic proxies, in centimetres. See stadium port report.
 * Layout: inner x/y/radius/height, outer x/y/radius/offset-x, centre x/y/full-ring/offset-y,
 * enabled panels (-X,+X,-Y,+Y). No texture lookup or per-frame fitting. */
static const float nx_shell_roofs[14][16] = {
  {0}, /* Konami retains its original skylight proxy. */
  {5650,4200,150,3000,11000,8500,250,0,0,0,0,0,1,1,1,1}, /* Anfield: unchanged v20. */
  {6300,4250,2150,4679.4,14600,12050,12050,0,150,0,0,0,1,1,1,1}, /* EtihadStadium */
  {5450,3650,350,5658.91,11850,10050,5650,0,0,0,0,0,1,1,1,1}, /* GiuseppeMeazza */
  {8650,5350,4200,2967.89,13350,10050,10050,0,0,0,0,0,1,1,1,1}, /* ParcdesPrinces */
  {9150,7150,4100,2740.76,10250,9050,6350,0,0,-200,0,0,1,1,1,1}, /* RamonSanchezPizjuan */
  {5450,3650,350,5658.91,11850,10050,5650,0,0,0,0,0,1,1,1,1}, /* SanSiro */
  {6500,2850,1450,6413.54,12800,14350,11250,0,-50,0,0,0,1,1,1,1}, /* SantiagoBernabeu */
  {5950,3650,350,3704.42,12250,9750,5200,0,0,0,0,0,1,1,1,1}, /* SignalIdunaPark */
  {6100,4400,1150,2891.99,11500,9500,9500,0,-50,-250,0,0,1,1,1,1}, /* StamfordBridge */
  {5800,4050,2050,4462.99,12900,9650,9650,0,-50,0,0,0,1,1,1,1}, /* TottenhamStadium */
  {6950,5350,5350,4317.1,13550,12550,11550,0,0,0,0,0,1,1,1,1}, /* WandaMetropolitano */
  {8850.0,5700.0,3150.0,3358.4,11700.0,9250.0,6350.0,-50.0,0.0,1550.0,0.0,-1850.0,1.0,1.0,1.0,1.0}, /* OldTrafford */
  {6550,4750,2950,4081.71,7900,9400,3000,0,0,0,0,0,0,0,0,1}, /* CampNou */
};
static inline void stadium_roof_uniform(unsigned id,float out[16]) {
  memcpy(out,nx_shell_roofs[id<sizeof(nx_shell_roofs)/sizeof(nx_shell_roofs[0])?id:0],16*sizeof(float));
  /* v29 art direction: overhead openings shift toward +X/+Y so shade covers
   * about 15% of the pitch along its left/lower sides. Keep the measured source
   * fit above for reproducible imports; these are runtime lighting changes,
   * not geometry or camera clearance. Bernabeu also widens its opening. */
  if(id==6) { out[8]=800.f; out[9]=900.f; }
  if(id==7) { out[1]=3250.f; out[8]=1850.f; out[9]=500.f; }
  /* Camp Nou has only the +Y stand roof. The requested side band shifts the
   * opening at uniform upload; the measured mesh fit remains above. */
  if(id==13) { out[3]=2600.f; out[9]=-2200.f; }
  /* Uniform decision once per profile, not four per-fragment panel branches. */
  out[10]=(out[12]>=.5f && out[13]>=.5f && out[14]>=.5f && out[15]>=.5f)?1.f:0.f;
}
static inline void stadium_roof_uniform_season(unsigned id,unsigned winter,float out[16]) {
  stadium_roof_uniform(id,out);
  /* Camp Nou's requested side band stays around a third of the field in
   * both seasons. Offset the taller winter projection at uniform upload,
   * preserving its light ray on bodies without new per-fragment work. */
  if(id==13 && winter==1u) out[9]+=650.f;
}
#endif
