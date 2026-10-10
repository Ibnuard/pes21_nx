#ifndef PESNX_STADIUM_CATALOG_H
#define PESNX_STADIUM_CATALOG_H
#include <string.h>
/* Preserve the playable pitch, goals, flags, billboards and player actors. */
static inline int stadium_shell_member(const char *name) {
  if (!name || !*name || !strncmp(name, "st029_pitch", 11)) return 0;
  return !strncmp(name, "st029_", 6) || !strncmp(name, "pitch_side", 10);
}
static inline const char *stadium_catalog_label(unsigned index) {
  return index == 1 ? "ANFIELD (TEST)" : "KONAMI STADIUM";
}
#endif
