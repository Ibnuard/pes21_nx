/* Diagnostic build only. No actor or component is retained beyond a numeric
 * token in a bounded record; do not inspect those tokens after Load returns.
 * Collection writes RAM only. Reporting runs outside live play. */
#ifdef NEAR_CAMERA_TRACE
typedef struct {
  uint64_t elapsed_ns;
  uint32_t native_id, ready, component[2], resolved[2], render_mesh[2], lods[2];
} RealfaceLoadRecord;
static RealfaceLoadRecord realface_load_records[128];
static uint32_t realface_load_count, realface_load_reported;
static void (*realface_load_original)(void *,const char *);

static void realface_load_probe(void *actor,const char *name) {
  const uint64_t begin=armGetSystemTick();
  realface_load_original(actor,name);
  const uint32_t index=__atomic_fetch_add(&realface_load_count,1u,__ATOMIC_RELAXED);
  if (index>=128u) return;
  RealfaceLoadRecord *r=&realface_load_records[index];
  r->elapsed_ns=armTicksToNs(armGetSystemTick()-begin);
  /* The supported loader's argument is the decimal native storage key. Do
   * not reinterpret it as the cross-update BaseId or guess player identity. */
  if (name && name[0]>='0' && name[0]<='9') r->native_id=(uint32_t)strtoul(name,NULL,10);
  for (unsigned i=0;i<2;++i) {
    void *component=NULL,*resolved=NULL,*mesh=NULL,*render=NULL;
    if (actor) {
      memcpy(&component,(const char *)actor+0x350+i*0x20,sizeof(component));
      memcpy(&resolved,(const char *)actor+0x358+i*0x20,sizeof(resolved));
    }
    r->component[i]=component!=NULL; r->resolved[i]=resolved!=NULL;
    if (component) {
      /* Match native GetNumLODs: the optional override at 0x6c0 is normally
       * null. SetSkeletalMesh stores the regular asset at 0x5a0. */
      memcpy(&mesh,(const char *)component+0x6c0,sizeof(mesh));
      if (!mesh) memcpy(&mesh,(const char *)component+0x5a0,sizeof(mesh));
    }
    r->render_mesh[i]=mesh!=NULL;
    if (mesh) memcpy(&render,(const char *)mesh+0x40,sizeof(render));
    if (render) memcpy(&r->lods[i],(const char *)render+8,sizeof(uint32_t));
  }
  __atomic_store_n(&r->ready,1u,__ATOMIC_RELEASE);
}
static void install_realface_load_probe(so_module *module) {
  const char *symbol="_ZN12APlayerActor12LoadRealFaceEPKc";
  const uintptr_t original=so_try_find_addr_rx(module,symbol);
  if (!original) return;
  static const char *const classes[]={
    "_ZTV16APlayerActorHigh","_ZTV15APlayerActorLow","_ZTV18APlayerActorLowest"};
  uintptr_t *slots[3];
  for (unsigned i=0;i<3;++i) {
    if (!so_try_find_addr_rx(module,classes[i])) return;
    slots[i]=find_vtable_method_slot(module,classes[i],original,224u);
    if (!slots[i]) return;
  }
  realface_load_original=(void *)original;
  for (unsigned i=0;i<3;++i) *slots[i]=(uintptr_t)&realface_load_probe;
}
void pes_controller_face_probe_report(void) {
  while (realface_load_reported<128u) {
    RealfaceLoadRecord *r=&realface_load_records[realface_load_reported];
    if (!__atomic_load_n(&r->ready,__ATOMIC_ACQUIRE)) break;
    char line[384];
    snprintf(line,sizeof(line),
      "v43 native_id=%u load_us=%llu face_component=%u face_resolved=%u face_mesh=%u face_lods=%u "
      "hair_component=%u hair_resolved=%u hair_mesh=%u hair_lods=%u (load snapshot; not a visibility pass)",
      r->native_id,(unsigned long long)(r->elapsed_ns/1000),
      r->component[0],r->resolved[0],r->render_mesh[0],r->lods[0],
      r->component[1],r->resolved[1],r->render_mesh[1],r->lods[1]);
    scene_runtime_note("realface-load",line); ++realface_load_reported;
  }
}
#endif
