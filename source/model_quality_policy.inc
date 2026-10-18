/* Saved Low=0, Standard=1, High=2. The native actor chooser uses Lowest, Low,
 * High respectively (internal value 3 also uses Lowest). Redirect ONLY its
 * High-class call to the existing Standard-class factory. The native body
 * mesh selector already treats 1/2 identically; the face PAK retains its LOD.
 * No global getter, stadium choice, material scalability or saved option is
 * replaced. Native Standard and Low paths remain byte-for-byte intact. */
static int model_quality_policy_installed;
#ifdef NEAR_CAMERA_TRACE
extern int pes_gl_probe_native_player_class(void);
#endif

static void install_model_quality_policy(so_module *module) {
  if (model_quality_policy_installed) return;
#ifdef NEAR_CAMERA_TRACE
  if (pes_gl_probe_native_player_class()) {
    scene_runtime_note("model quality", "diagnostic control: native player classes; saved quality and stadium unchanged");
    return;
  }
#endif
  const char *symbol = "_ZN13UEPlayerModel8LoadImplEv";
  static const uint32_t expected[4] = {
    0x97e7b0a3, 0xaa0003f6, 0x910023e0, 0x97e85630,
  };
  if (!so_try_find_addr_rx(module, symbol)) goto unavailable;
  const uintptr_t backing = so_find_addr(module, symbol);
  if (!backing || memcmp((const void *)(backing + 0xd4), expected,
                         sizeof(expected))) goto unavailable;
  /* bl APlayerActorLow::GetPrivateStaticClass@plt, same class used at +0xb0.
   * Installation precedes engine threads and the loader's RX cache flush. */
  *(uint32_t *)(backing + 0xd4) = 0x97e4ec7b;
  model_quality_policy_installed = 1;
  scene_runtime_note("model quality", "LOW=low/low STANDARD=standard/standard HIGH=standard/high (player/stadium)");
  return;
unavailable:
  scene_runtime_note("model quality", "native fallback; High player-class fingerprint unavailable");
}
