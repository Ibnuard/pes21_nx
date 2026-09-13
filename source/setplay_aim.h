#pragma once
#include <math.h>
static inline float pes_setplay_wrap_angle(float degrees) {
  degrees = fmodf(degrees, 360.0f);
  return degrees < 0 ? degrees + 360.0f : degrees;
}
static inline float pes_setplay_camera_heading(float look_x, float look_z,
                                               float camera_x, float camera_z) {
  return pes_setplay_wrap_angle(atan2f(look_x - camera_x, look_z - camera_z)
                                * 57.2957795131f);
}
// Native mobile kick stores a polar swipe vector at +0x44/+0x48. A lateral
// vector uses 90/270 degrees and a normalized magnitude, not a new aim angle.
static inline void pes_setplay_curl_command(float curl, float *angle, float *power) {
  curl = fmaxf(-1, fminf(1, curl));
  *angle = curl < 0 ? 90.0f : curl > 0 ? 270.0f : 0.0f;
  *power = fabsf(curl);
}
static inline void pes_setplay_bend_point(float *x, float *z, float dx, float dz,
                                         float distance, float curl, float t) {
  // Zero slope at the ball: LS-X bends the flight, never rotates its launch.
  const float bend = distance * 0.14f * curl * t * t;
  *x -= dz * bend;
  *z += dx * bend;
}

// A lateral sweep is curl intent, not a new (usually much lower) elevation.
// libnx Y is positive upwards. Keep pitch in that same world-up convention.
static inline int pes_setplay_height_intent(float x, float y) {
  return fabsf(y) > 0.15f && fabsf(y) >= fabsf(x);
}

// The mirror of height intent, and for the same reason: a stick that has been
// released reports neutral, which is not a request to straighten the flight.
// Without this gate curl was rewritten from LS-X every frame, so the selected
// curve survived only while the stick was physically held, while height (which
// has always been gated) stayed latched.
static inline int pes_setplay_curl_intent(float x, float y) {
  return fabsf(x) > 0.15f && fabsf(x) > fabsf(y);
}
