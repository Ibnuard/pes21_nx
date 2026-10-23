/* Native input adapter. Runs only on the model/input callback thread. Layouts
 * and enum conversions are admitted against bounded compatible-ELF bodies. */
static uintptr_t corner_native_vptr[2],corner_native_units[2];
static uint32_t (*corner_defence_original)(void *,const void *,uint32_t);
static const void *(*corner_get_anime)(const void *,uint32_t);
static uint32_t (*corner_is_setplay_anime)(uint32_t);
static int corner_native_enabled;
typedef struct {
  uintptr_t match;
  uint32_t session,restart,kicker,mode,normal,short_choice,defence;
} CornerNativeContext;
static CornerNativeContext corner_native_last[2];
static uint64_t corner_native_epochs[2];

/* Hook installation precedes so_finalize: load_virtbase is only a future
 * call address here. Read bounded opcode/table bytes from load_base instead;
 * keep the RX alias solely for stored function and relocated vptr values. */
static uintptr_t corner_native_backing_symbol(so_module *module,
    const char *name,size_t bytes,uintptr_t *runtime) {
  if(!module || !module->load_base || !module->load_virtbase || !runtime ||
     !bytes || bytes>module->load_size)return 0;
  const uintptr_t rx=so_try_find_addr_rx(module,name);
  const uintptr_t alias=(uintptr_t)module->load_virtbase;
  if(!rx || rx<alias || rx-alias>module->load_size-bytes)return 0;
  *runtime=rx;
  return (uintptr_t)module->load_base+(rx-alias);
}

static int corner_native_context(const void *input,uint32_t pad,
                                  CornerNativeContext *out) {
  memset(out,0,sizeof(*out));
  if(!corner_native_enabled || !input || pad>1 ||
     !pes_controller_native_pad_lab_active() ||
     (pad && !pes_controller_native_pad_lab_two_player()))return 0;
  uint32_t player;
  memcpy(&player,(const char *)input+0x24,4);
  if(player>21 || (player>=11)!=pad)return 0;
  const void *registry=match_global_registry_get_instance();
  const void *info=NULL;
  if(registry)memcpy(&info,(const char *)registry+0x4f0,sizeof(info));
  if(!info)return 0;
  uint32_t status;
  memcpy(&status,(const char *)info+0x116c,4);
  memcpy(&out->restart,(const char *)info+0x1514,4);
  memcpy(&out->kicker,(const char *)info+0x16fc,4);
  if(status!=3 || (out->restart!=4 && out->restart!=5) ||
      out->kicker>21)return 0;
  const void *anime=corner_get_anime(registry,out->kicker);
  if(!anime || !corner_is_setplay_anime(*((const uint8_t *)anime+1)))return 0;
  const void *ai=match_global_registry_get_team_ai_info(registry,pad);
  if(!ai)return 0;
  memcpy(&out->normal,(const char *)ai+0xb8a8,4);
  memcpy(&out->short_choice,(const char *)ai+0xb8ac,4);
  memcpy(&out->defence,(const char *)ai+0xb8b0,4);
  if(out->normal>8 || out->short_choice>4 || out->defence>2)return 0;
  out->mode=(out->kicker>=11)==pad ? FNX_CORNER_ATTACK : FNX_CORNER_DEFENCE;
  out->match=(uintptr_t)info;
  out->session=__atomic_load_n(&match_hud_session_serial,__ATOMIC_ACQUIRE);
  return 1;
}
static int corner_native_same(const CornerNativeContext *a,
                              const CornerNativeContext *b) {
  return a->match==b->match && a->session==b->session &&
      a->restart==b->restart && a->kicker==b->kicker && a->mode==b->mode;
}
static uint32_t corner_native_observe(void *list,const void *input,uint32_t pad) {
  CornerNativeContext context;
  if(pad>1)return 0;
  int valid=corner_native_context(input,pad,&context);
  uint32_t kind=valid && context.mode==FNX_CORNER_DEFENCE ? 71 : 70;
  uintptr_t unit=0,vptr=0;
  if(valid && list) {
    memcpy(&unit,(const char *)list+0x3bf8+kind*sizeof(uintptr_t),sizeof(unit));
    if(unit)memcpy(&vptr,(const void *)unit,sizeof(vptr));
    valid=unit && vptr==corner_native_vptr[kind==71];
  } else valid=0;
  if(!valid)memset(&context,0,sizeof(context));
  if(!corner_native_same(&context,&corner_native_last[pad]) ||
     corner_native_units[pad]!=(valid ? unit : 0))
    ++corner_native_epochs[pad];
  corner_native_last[pad]=context;
  corner_native_units[pad]=valid ? unit : 0;
  fnx_corner_publish(pad,corner_native_epochs[pad],context.mode,
      context.restart==4,context.normal,context.short_choice,context.defence,
      scene_runtime_ms());
  return valid ? kind : 0;
}
static uint32_t corner_native_main(void *unit,const void *input,uint32_t kind,
    uint32_t (*original)(void *,const void *,uint32_t)) {
  uint32_t player=UINT32_MAX;
  if(input)memcpy(&player,(const char *)input+0x24,4);
  uint32_t pad=player<11 ? 0 : 1;
  CornerNativeContext context;
  int owned=unit && player<=21 && corner_native_units[pad]==(uintptr_t)unit &&
      corner_native_context(input,pad,&context) &&
      corner_native_same(&context,&corner_native_last[pad]);
  /* Preserve native Init/lifecycle, but suppress its hidden camera-dependent
   * menu. The custom selector owns both direction and option encoding. */
  if(owned)memset((char *)unit+0x38,0,2);
  uint32_t result=original ? original(unit,input,kind) : 0;
  if(!owned)return result;
  memset((char *)unit+0x38,0,2);
  uint32_t command=0;uint8_t option=0;
  if(fnx_corner_take(pad,corner_native_epochs[pad],scene_runtime_ms(),
                     &command,&option)) {
    memcpy((char *)unit+0x19,&option,1);
    char note[96];snprintf(note,sizeof(note),
        "v69 native command: pad=%u command=%u option=%u",pad,command,option);
    scene_runtime_note("corner tactics",note);
    return command;
  }
  return 0;
}
static uint32_t corner_native_defence_main(void *unit,const void *input,uint32_t kind) {
  return corner_native_main(unit,input,kind,corner_defence_original);
}
static void install_corner_tactics(so_module *module) {
  corner_native_enabled=0;
  static const struct {const char *name;uint32_t size,hash;} guards[]={
    {"_ZN5match8registry10PadCommand21ConvertOption2TacticsEh",44,0xb20d6bd1u},
    {"_ZN5match8registry10PadCommand25ConvertOption2DefenceTypeEh",28,0x8d31d004u},
    {"_ZN5match3pad30ThinkUnitCornerKickDefenceType4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE",508,0xa0216015u},
    {"_ZN5match8registry10PadCommand32ConvertOption2ShortCornerTacticsEh",28,0x9bb8a272u},
    {"_ZN5match3pad26ThinkUnitCornerKickTactics4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE",600,0x79841024u},
    {"_ZN5match2ai4Team27UpdateCornerKickDefenceTypeEv",408,0xdbc9994du},
    {"_ZN5match2ai4Team23UpdateCornerKickTacticsEv",824,0xb39e6a4bu}};
  for(unsigned i=0;i<sizeof(guards)/sizeof(guards[0]);i++) {
    uintptr_t runtime=0;
    const uint8_t *body=(const void *)corner_native_backing_symbol(module,
        guards[i].name,guards[i].size,&runtime);
    uint32_t hash=2166136261u;
    if(!body)goto unavailable;
    for(uint32_t j=0;j<guards[i].size;j++)hash=(hash^body[j])*16777619u;
    if(hash!=guards[i].hash)goto unavailable;
  }
  uintptr_t anime=0,setplay=0,attack=0,defence=0,main=0;
  if(!corner_native_backing_symbol(module,
      "_ZNK5match8registry14GlobalRegistry12GetAnimeInfoE8PlayerNo",4,&anime) ||
     !corner_native_backing_symbol(module,
      "_ZN5match8registry22IsSetPlayMoveAnimeKindENS_15AnimeActionKindE",4,&setplay) ||
     !corner_native_backing_symbol(module,
      "_ZTVN5match3pad26ThinkUnitCornerKickTacticsE",16,&attack) ||
     !corner_native_backing_symbol(module,
      "_ZTVN5match3pad30ThinkUnitCornerKickDefenceTypeE",20*sizeof(uintptr_t),&defence) ||
     !corner_native_backing_symbol(module,guards[2].name,guards[2].size,&main))
    goto unavailable;
  uintptr_t *slot=find_vtable_method_slot(module,
      "_ZTVN5match3pad30ThinkUnitCornerKickDefenceTypeE",main,20);
  if(!slot || !match_global_registry_get_instance ||
      !match_global_registry_get_team_ai_info)goto unavailable;
  corner_get_anime=(void *)anime;corner_is_setplay_anime=(void *)setplay;
  corner_native_vptr[0]=attack+16;corner_native_vptr[1]=defence+16;
  corner_defence_original=(void *)main;
  *slot=(uintptr_t)&corner_native_defence_main;
  corner_native_enabled=1;
  scene_runtime_note("corner tactics","v70 bounded RW guards passed; native attack/short/defence admitted; LEFT menu, RIGHT taker");
  return;
unavailable:
  scene_runtime_note("corner tactics","v70 optional native ABI unavailable; stock controls retained");
}
