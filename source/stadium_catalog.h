#ifndef PESNX_STADIUM_CATALOG_H
#define PESNX_STADIUM_CATALOG_H
#include <string.h>
/* Preserve the playable pitch, goals, flags, billboards and player actors. */
static inline int stadium_shell_member(const char *name) {
  if (!name || !*name || !strncmp(name, "st029_pitch", 11)) return 0;
  return !strncmp(name, "st029_", 6) || !strncmp(name, "pitch_side", 10);
}
/* Stable IDs; installed menu indices are resolved by the runtime registry. */
#define NX_STADIUM_COUNT 14u
typedef struct {
  const char *label, *package, *mesh, *object;
} NxStadiumEntry;
#define NX_SHELL(key, title, pak) {title, "PesMobile/Content/Paks/" pak, \
  key "Shell", "/Game/FootballNX/Stadiums/" key "/" key "Shell." key "Shell"}
static const NxStadiumEntry nx_stadium_catalog[NX_STADIUM_COUNT] = {
  {"KONAMI STADIUM", "", "st029_b", "/Game/Assets/bg_lighting_AM1/Meshes/st029_b.st029_b"},
  NX_SHELL("Anfield", "ANFIELD STADIUM", "PesMobile-Anfield-Android_ETC1_P.pak"),
  NX_SHELL("EtihadStadium", "ETIHAD STADIUM", "PesMobile-EtihadStadium-Android_ETC1_P.pak"),
  NX_SHELL("GiuseppeMeazza", "GIUSEPPE MEAZZA", "PesMobile-GiuseppeMeazza-Android_ETC1_P.pak"),
  NX_SHELL("ParcdesPrinces", "PARC DES PRINCES", "PesMobile-ParcdesPrinces-Android_ETC1_P.pak"),
  NX_SHELL("RamonSanchezPizjuan", "RAMON SANCHEZ PIZJUAN", "PesMobile-RamonSanchezPizjuan-Android_ETC1_P.pak"),
  NX_SHELL("SanSiro", "SAN SIRO", "PesMobile-SanSiro-Android_ETC1_P.pak"),
  NX_SHELL("SantiagoBernabeu", "SANTIAGO BERNABEU", "PesMobile-SantiagoBernabeu-Android_ETC1_P.pak"),
  NX_SHELL("SignalIdunaPark", "SIGNAL IDUNA PARK", "PesMobile-SignalIdunaPark-Android_ETC1_P.pak"),
  NX_SHELL("StamfordBridge", "STAMFORD BRIDGE", "PesMobile-StamfordBridge-Android_ETC1_P.pak"),
  NX_SHELL("TottenhamStadium", "TOTTENHAM HOTSPUR STADIUM", "PesMobile-TottenhamStadium-Android_ETC1_P.pak"),
  NX_SHELL("WandaMetropolitano", "WANDA METROPOLITANO", "PesMobile-WandaMetropolitano-Android_ETC1_P.pak"),
  NX_SHELL("OldTrafford", "OLD TRAFFORD", "PesMobile-OldTrafford-Android_ETC1_P.pak"),
  NX_SHELL("CampNou", "CAMP NOU", "PesMobile-CampNou-Android_ETC1_P.pak")
};
#undef NX_SHELL
/* Keep historical IDs for logs and safe restoration of an old shell, but do
 * not offer retired packages even when their files remain on the SD card. */
static inline int stadium_catalog_selectable(unsigned id) {
  return id<=2 || id==8 || id==9 || id==12 || id==13;
}
static inline const char *stadium_catalog_label(unsigned id) {
  return nx_stadium_catalog[id < NX_STADIUM_COUNT ? id : 0].label;
}
static inline int stadium_imported_mesh(const char *name) {
  for (unsigned i=1; i<NX_STADIUM_COUNT; ++i)
    if (!strcmp(name,nx_stadium_catalog[i].mesh)) return 1;
  return 0;
}
#endif
