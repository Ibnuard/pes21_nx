#ifndef PESNX_REFEREE_PC_POLICY_H
#define PESNX_REFEREE_PC_POLICY_H

#include <math.h>
#include <stddef.h>

/* The two final target constraints recovered from the owned FL26 x64
 * RefereeChief routine. Inputs are semantic FieldInfo values, not PC object
 * offsets or hardcoded guesses about PC pitch dimensions. The surrounding
 * target selection, animation and match decisions are separate policies. */
typedef struct {
  float half_width;
  float penalty_line_x;
  float penalty_half_width;
} RefereePcField;

static inline int referee_pc_field_valid(RefereePcField field) {
  return isfinite(field.half_width) && isfinite(field.penalty_line_x) &&
      isfinite(field.penalty_half_width) && field.half_width > 0.0f &&
      field.half_width < 100.0f && field.penalty_line_x > 3.0f &&
      field.penalty_line_x < 100.0f && field.penalty_half_width > 0.0f &&
      field.penalty_half_width < field.half_width;
}

static inline int referee_pc_bound_live_target(float *x, float *z,
                                                RefereePcField field) {
  if (!x || !z || !isfinite(*x) || !isfinite(*z) ||
      !referee_pc_field_valid(field)) return 0;

  /* FL26 RVA a37de6..a37e21: keep the live target three metres inside the
   * penalty-area line. This uses FieldInfo+18, not the halfway pitch length. */
  const float end_limit = field.penalty_line_x - 3.0f;
  if (fabsf(*x) > end_limit) *x = *x < 0.0f ? -end_limit : end_limit;

  /* FL26 RVA a382a0..a38302. The width around this diagonal is the FIELD
   * half width; the line's slope uses the penalty-area X/Z dimensions. */
  const float diagonal_z = field.penalty_half_width -
      ((field.penalty_line_x + *x) * field.penalty_half_width /
       field.penalty_line_x);
  const float relative_z = *z - diagonal_z;
  if (fabsf(relative_z) > field.half_width)
    *z = diagonal_z + (relative_z < 0.0f ? -field.half_width : field.half_width);
  return 1;
}

#endif
