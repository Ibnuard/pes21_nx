#ifndef PES_STADIUM_VIEW_POLICY_H
#define PES_STADIUM_VIEW_POLICY_H
#include <math.h>

// Stadium-scale tribune, Y-up. V11's 35-50m eye / 22-25m half-span produced
// an eagle-eye view. Native Stadium D2/H6 uses Y=17.68/Z=55: stay close to
// that rail, with a small far-side lift and controlled near-side magnification.
static inline unsigned footballnx_tribune_view(float *p) {
  if (!p) return 0;
  for (unsigned i=0; i<6; ++i) if (!isfinite(p[i])) return 0;
  if (fabsf(p[0]) > 80.0f || fabsf(p[2]) > 45.0f ||
      p[1] < -5.0f || p[1] > 10.0f) return 0;
  p[3] = p[0];
  p[5] = 55.0f;
  const float across = p[5] - p[2];
  const float elevation = 18.0f + 0.025f * across;
  p[4] = p[1] + elevation;
  const float near = fminf(1.0f, fmaxf(0.0f, (p[2] + 34.0f) / 68.0f));
  const float half_span = 9.5f + 1.5f * near * near * (3.0f - 2.0f * near);
  // CameraParameter+0x34 is vertical FOV in radians (native degrees*pi/180).
  // Absolute mapping is idempotent; no state survives a camera change.
  p[13] = 2.0f * atanf(half_span / hypotf(across, elevation));
  return 1;
}
#endif
