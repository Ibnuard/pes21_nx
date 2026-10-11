/* Opt-in visual referee follower. The native Mobile match factory creates only
 * 22 players. Load a separate HumanKind=Referee and play retargeted EF10
 * clips in its OWN bone buffer with an independent animation clock.
 * Positioning is authored in the wrapper;
 * it does not replace match decisions or add a player to registries/collision.
 * Enable with the exact token in referee-probe.txt. */
#include "referee_motion.h"
#include "referee_animation.h"
#include "match_environment.h"
#include "scene_runtime_log.h"
typedef struct { uint64_t words[21]; } RefereeProbeLoadId;
typedef struct { float x, y, z, pad; } RefereeProbeVector;
typedef struct { float x, y, z; } RefereeNativeVector;
static RefereeProbeLoadId (*referee_create_id)(uint32_t, uint32_t, uint32_t, uint32_t);
static uint32_t (*referee_get_id)(void *, uint32_t);
static void *(*referee_new)(size_t);
static void (*referee_ctor)(void *, uint32_t, const RefereeProbeLoadId *);
static void (*referee_delete)(void *);
static int (*referee_init)(void *);
static float (*referee_root_scale)(const void *);
static void (*referee_update)(void *, const RefereeProbeVector *, float,
                              const RefereeProbeVector *);
static void (*referee_display)(void *, int);
static void (*referee_draw_original)(void *);
static int (*referee_create_model_original)(void *, const RefereeProbeLoadId *);
static int (*referee_all_loaded_original)(void *);
static int (*referee_uniform_busy)(void);
static void (*referee_set_lod)(void *, uint32_t, float, float);
static void (*referee_release_original)(void *);
static void (*referee_unload_original)(void *);
static void (*referee_destroy_loader_original)(void *);
static void (*referee_loaded_original)(void *);
static void (*referee_out_original)(void *, const void *, const void *);
static void (*referee_animation_release_original)(void);
static int (*referee_manager_create_original)(void);
static void (*referee_publish_bones)(void *, const void *);
static void *(*referee_registry)(void);
static const void *(*referee_player_move)(const void *, uint32_t);
static const float *(*referee_ball_trans)(const void *);
static uint64_t (*referee_frame_stamp)(void);
static void (*referee_reset_flow_original)(void *,uint32_t);
static void (*referee_demo_transform_original)(void *,float *,float *,uint32_t,uint8_t,uint8_t,float,float);
static int (*referee_match_faded)(const void *);
static uint32_t referee_kickoff_pending;
static uint32_t referee_kickoff_ready;
static uint32_t referee_demo_sequence;
static uint64_t referee_demo_tick;
static int32_t referee_demo_x,referee_demo_z,referee_demo_heading;
static void *referee_probe_model;
static uint32_t referee_probe_enabled, referee_probe_frames, referee_probe_ready;
static uint32_t referee_probe_failed, referee_probe_moved, referee_probe_has_pose;
static uint32_t referee_probe_live_frame;
static uint32_t referee_probe_teardown;
static uint32_t referee_probe_pending, referee_probe_loaded;
static uint64_t referee_probe_load_tick;
static uint32_t referee_probe_scene_ready, referee_probe_scene_loading;
static uint64_t referee_probe_event;
static uint64_t referee_probe_event_key;
static uint32_t referee_probe_whistle_serial,referee_probe_whistle_seen;
static uint64_t referee_probe_whistle_handle;
static void (*referee_sound_original)(const void *,uint64_t,const uint8_t *,uint32_t,const void *,uint32_t);
static RefereeGesture referee_gesture;
static RefereeMotion referee_motion;
static uint64_t referee_probe_stamp, referee_probe_frame;
static RefereeAnimationBank referee_animation_bank;
static RefereeAnimationClock referee_animation_clock;
static float referee_probe_dt;
#ifndef PESNX_REFEREE_PROBE_HOST_TEST
static void *referee_animation_data;
#endif
static uint64_t referee_probe_tick;
static int referee_probe_display_valid, referee_probe_display_value;
static RefereePoint referee_player_snapshot[22];
static uint32_t referee_player_snapshot_count;
static uint64_t referee_player_snapshot_tick;
static int referee_player_snapshot_valid;
/* Atomic scalar hand-off only: no HUD/model pointer crosses threads. The
 * existing native name renderer projects our current torso with its camera. */
static uint64_t referee_screen_sample,referee_world_point,referee_world_tick;
static uint32_t referee_using_demo;
static struct {
  uint64_t samples, follow_ns, pose_ns, publish_ns, update_ns, worst_ns, player_reads;
  uint64_t culled;
} referee_perf;
static uint32_t referee_perf_sequence;
static uint64_t referee_perf_snapshot[8];

static uint64_t referee_elapsed_ns(uint64_t start,uint64_t end) {
  return end>=start ? armTicksToNs(end-start) : 0;
}
static void referee_perf_publish(void) {
  if (!referee_perf.samples) return;
  const uint64_t values[8]={referee_perf.samples,referee_perf.follow_ns/referee_perf.samples/1000,
    referee_perf.pose_ns/referee_perf.samples/1000,referee_perf.publish_ns/referee_perf.samples/1000,
    referee_perf.update_ns/referee_perf.samples/1000,referee_perf.worst_ns/1000,
    referee_perf.player_reads,referee_perf.culled};
  __atomic_fetch_add(&referee_perf_sequence,1,__ATOMIC_ACQ_REL);
  for(unsigned i=0;i<8;i++)__atomic_store_n(&referee_perf_snapshot[i],values[i],__ATOMIC_RELAXED);
  __atomic_fetch_add(&referee_perf_sequence,1,__ATOMIC_RELEASE);
}
/* Called alongside the overlay's existing presentation summary at a break.
 * Periodic CPU logs do not add SD-card I/O to the live follower update. */
void pes_controller_referee_performance_note(void) {
  static uint32_t last;
  const uint32_t sequence=__atomic_load_n(&referee_perf_sequence,__ATOMIC_ACQUIRE);
  if(!sequence || (sequence&1u) || sequence==last)return;
  uint64_t values[8];
  for(unsigned i=0;i<8;i++)values[i]=__atomic_load_n(&referee_perf_snapshot[i],__ATOMIC_RELAXED);
  __atomic_thread_fence(__ATOMIC_ACQUIRE);
  if(sequence!=__atomic_load_n(&referee_perf_sequence,__ATOMIC_RELAXED))return;
  last=sequence;
  char text[320];
  snprintf(text,sizeof(text),"v17 samples=%llu follow_avg_us=%llu pose_avg_us=%llu publish_avg_us=%llu update_avg_us=%llu cpu_worst_us=%llu player_reads=%llu offscreen=%llu whistles=%u (CPU only; excludes native draw/GPU)",
      (unsigned long long)values[0],(unsigned long long)values[1],(unsigned long long)values[2],
      (unsigned long long)values[3],(unsigned long long)values[4],(unsigned long long)values[5],
      (unsigned long long)values[6],(unsigned long long)values[7],
      __atomic_load_n(&referee_probe_whistle_serial,__ATOMIC_ACQUIRE));
  scene_runtime_note("referee perf",text);
}
static void referee_perf_flush(void) {
  referee_perf_publish();
  memset(&referee_perf,0,sizeof(referee_perf));
}
static void referee_perf_record(uint64_t start,uint64_t follow,uint64_t pose,uint64_t publish,uint64_t end) {
  ++referee_perf.samples;
  referee_perf.follow_ns+=referee_elapsed_ns(start,follow);
  referee_perf.pose_ns+=referee_elapsed_ns(follow,pose);
  referee_perf.publish_ns+=referee_elapsed_ns(pose,publish);
  referee_perf.update_ns+=referee_elapsed_ns(publish,end);
  const uint64_t cost=referee_elapsed_ns(start,end);
  if(cost>referee_perf.worst_ns)referee_perf.worst_ns=cost;
  if(referee_perf.samples%60u==0)referee_perf_publish();
}
static int referee_probe_offscreen(int scene,uint64_t now) {
  if(scene!=2 || referee_using_demo || referee_kickoff_ready || !referee_probe_has_pose)return 0;
  const uint64_t sample=__atomic_load_n(&referee_screen_sample,__ATOMIC_ACQUIRE),tick=sample>>1;
  /* Missing, stale or regressed observations always leave the model visible. */
  return (sample&1u) && tick && now>=tick && referee_elapsed_ns(tick,now)<50000000ull;
}

static void referee_probe_set_display(int visible) {
  if (!referee_probe_model) return;
  // Native SetDisp enqueues a heap-allocated timestamped command. Visibility
  // persists until the next command; repeating it every write frame needlessly
  // fills the render queue, including while a paused renderer is not consuming.
  if (referee_probe_display_valid && referee_probe_display_value==visible) return;
  referee_display(referee_probe_model,visible);
  referee_probe_display_value=visible;
  referee_probe_display_valid=1;
}

static void referee_probe_note(const char *text) {
  scene_runtime_note("referee",text);
#ifndef PESNX_REFEREE_PROBE_HOST_TEST
  FILE *file = fopen("referee-probe.status", "w");
  if (file) { fputs(text, file); fputc('\n', file); fclose(file); }
#else
  (void)text;
#endif
}
static void referee_probe_clear(void) {
  referee_perf_flush();
  __atomic_store_n(&referee_screen_sample,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_world_tick,0,__ATOMIC_RELEASE);
  referee_using_demo=0;
  referee_player_snapshot_valid=0;
  if (referee_probe_model) {
    void *model = referee_probe_model;
    referee_probe_model = NULL;
    scene_runtime_note("referee","owned model release begin");
    referee_display(model, 0);
    referee_delete(model); // Native deleting destructor/allocator.
    scene_runtime_note("referee","owned model release returned");
  }
  referee_probe_frames = referee_probe_ready = referee_probe_failed = 0;
  referee_probe_pending = referee_probe_loaded = 0;
  referee_probe_load_tick = 0;
  referee_probe_moved = referee_probe_has_pose = 0;
  referee_probe_live_frame=0;
  referee_probe_stamp = referee_probe_frame = 0;
  referee_probe_tick = 0;
  referee_probe_display_valid=0;
  referee_animation_clock=(RefereeAnimationClock){0};
  referee_probe_dt=0;
  __atomic_store_n(&referee_kickoff_pending,0,__ATOMIC_RELEASE);
  referee_kickoff_ready=0;
  __atomic_store_n(&referee_demo_tick,0,__ATOMIC_RELEASE);
  referee_gesture=(RefereeGesture){0};
  referee_probe_whistle_seen=0;
  __atomic_store_n(&referee_probe_whistle_serial,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_whistle_handle,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_event,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_event_key,0,__ATOMIC_RELEASE);
  referee_motion_reset(&referee_motion);
}
static void referee_probe_reset_flow(void *flow,uint32_t kind) {
  referee_reset_flow_original(flow,kind);
  /* InitKickOffFlow calls ResetFlow(3), then queues the native fade-out. */
  __atomic_store_n(&referee_kickoff_pending,kind==3u,__ATOMIC_RELEASE);
}
static void referee_probe_demo_transform(void *self,float *position,float *rotation,
    uint32_t human,uint8_t frame,uint8_t mode,float time,float blend) {
  referee_demo_transform_original(self,position,rotation,human,frame,mode,time,blend);
  /* HumanList::AddReferee uses IDs 0x100..0x104. Only the centre referee
   * owns this follower; never borrow a player's or assistant's transform. */
  if(human!=0x100u || !position || !rotation || !referee_probe_enabled || referee_probe_teardown)return;
  /* A missing demo actor leaves the caller's outputs unchanged. Confirm that
   * the audited vector actually contains this actor before reading them. */
  uintptr_t begin=0,end=0,actor=0;
  if(!self)return;
  memcpy(&begin,(const char *)self+0xce0,sizeof(begin));
  memcpy(&end,(const char *)self+0xce8,sizeof(end));
  if(!begin || end<begin || (end-begin)%sizeof(void *) ||
      (end-begin)/sizeof(void *)<=human || (end-begin)/sizeof(void *)>4096)return;
  memcpy(&actor,(const void *)(begin+human*sizeof(void *)),sizeof(actor));
  if(!actor)return;
  float norm=0;for(uint32_t i=0;i<4;i++)norm+=rotation[i]*rotation[i];
  if(!isfinite(norm) || fabsf(norm-1.f)>.10f || !isfinite(position[1]) || fabsf(position[1])>5.f ||
      !referee_point_valid((RefereePoint){position[0],position[2]}) ||
      fabsf(position[0])>65.f || fabsf(position[2])>45.f)return;
  const float heading=atan2f(2.f*(rotation[3]*rotation[1]+rotation[0]*rotation[2]),
      1.f-2.f*(rotation[1]*rotation[1]+rotation[2]*rotation[2]));
  uint32_t sequence=__atomic_load_n(&referee_demo_sequence,__ATOMIC_RELAXED);
  if((sequence&1u) || !__atomic_compare_exchange_n(&referee_demo_sequence,&sequence,
      sequence+1,0,__ATOMIC_ACQ_REL,__ATOMIC_RELAXED))return;
  __atomic_store_n(&referee_demo_x,(int32_t)lrintf(position[0]*1000),__ATOMIC_RELAXED);
  __atomic_store_n(&referee_demo_z,(int32_t)lrintf(position[2]*1000),__ATOMIC_RELAXED);
  __atomic_store_n(&referee_demo_heading,(int32_t)lrintf(heading*1000),__ATOMIC_RELAXED);
  __atomic_store_n(&referee_demo_tick,armGetSystemTick(),__ATOMIC_RELEASE);
  __atomic_store_n(&referee_demo_sequence,sequence+2,__ATOMIC_RELEASE);
}
static void referee_probe_hidden_kickoff(void) {
  if(!__atomic_load_n(&referee_kickoff_pending,__ATOMIC_ACQUIRE) || !referee_match_faded)return;
  const void *registry=referee_registry(),*info=NULL;
  if(registry)memcpy(&info,(const char *)registry+0x4f0,sizeof(info));
  /* Native ExecFadeOut sets this only after its countdown finishes. */
  if(!info || !referee_match_faded(info))return;
  referee_motion_reset(&referee_motion);
  referee_motion.position=(RefereePoint){0,10};referee_motion.heading=3.141592654f;
  referee_kickoff_ready=1;
  referee_animation_clock=(RefereeAnimationClock){0};referee_gesture=(RefereeGesture){0};
  referee_probe_tick=0;referee_probe_dt=0;referee_player_snapshot_valid=0;
  __atomic_store_n(&referee_demo_tick,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_kickoff_pending,0,__ATOMIC_RELEASE);
  scene_runtime_note("referee","kickoff ready position applied behind completed native fade");
}
static void referee_probe_release(void *manager) {
  scene_runtime_note("referee","human manager release begin");
  referee_probe_teardown=1;
  __atomic_store_n(&referee_probe_scene_ready,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,0,__ATOMIC_RELEASE);
  referee_probe_clear();
  referee_release_original(manager);
}
static void referee_probe_animation_release(void) {
  // Manager::Destroy releases animation and all load groups BEFORE it calls
  // HumanLoadManager::Release. A draw::Human destructor still needs those
  // groups for Manager::Unload, so the old late hook alone was unsafe.
  referee_probe_teardown=1;
  __atomic_store_n(&referee_probe_scene_ready,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,0,__ATOMIC_RELEASE);
  referee_probe_clear();
  referee_probe_note("Referee v11 released before native animation/load groups.");
  referee_animation_release_original();
}
static int referee_probe_manager_create(void) {
  // Native Create is idempotent, including during event/demo setup. It is
  // NOT a scene boundary. Reloading here churned resources in visible demos.
  const int ready=referee_manager_create_original();
  if (ready) {
    const int notify=referee_probe_teardown || !referee_probe_scene_ready;
    referee_probe_teardown=0;
    if(notify)referee_probe_note("Referee v17 native model manager available.");
  }
  return ready;
}
static void referee_probe_unload(void *loader) {
  scene_runtime_note("referee","stadium unload begin");
  referee_probe_teardown=1;
  __atomic_store_n(&referee_probe_scene_ready,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,0,__ATOMIC_RELEASE);
  referee_probe_clear();
  referee_unload_original(loader);
  scene_runtime_note("referee","stadium unload returned");
}
static void referee_probe_destroy_loader(void *loader) {
  // Mobile's level exit uses DestroyLoader rather than UnLoad. Retire the
  // follower before the level and its render entities can disappear.
  referee_probe_note("Referee v11 stadium loader destruction; retiring follower.");
  referee_probe_teardown=1;
  __atomic_store_n(&referee_probe_scene_ready,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,0,__ATOMIC_RELEASE);
  referee_probe_clear();
  referee_destroy_loader_original(loader);
  scene_runtime_note("referee","stadium loader destruction returned");
}
static void referee_probe_loaded_scene(void *loader) {
  // A real stadium boundary, unlike an individual player's destructor. Stop
  // preloading until the native load AND the optional shell replacement end.
  __atomic_store_n(&referee_probe_scene_ready,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,1,__ATOMIC_RELEASE);
  const uint32_t pending=referee_probe_pending;
  referee_probe_clear();referee_probe_pending=pending;
  referee_probe_teardown=0;
  referee_loaded_original(loader);
  __atomic_store_n(&referee_probe_scene_ready,1,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_probe_scene_loading,0,__ATOMIC_RELEASE);
  referee_probe_note("Referee v11 stadium ready; model lifetime follows this stadium.");
}
static void referee_probe_out_of_play(void *record,const void *registry,const void *judge) {
  referee_out_original(record,registry,judge);
  if (!record || !judge || !referee_probe_enabled || referee_probe_teardown) return;
  // Only finalized ObserverOutOfPlay records, never predictive foul checks.
  // Copy scalar event metadata; retain no registry or judge pointers.
  uint32_t restart,reason;
  memcpy(&restart,judge,4);memcpy(&reason,(const char *)judge+0x20,4);
  if (restart>7 || reason>9) return;
  // The sole native call site passes RecordEvent+0x14 (guarded below).
  // Its start-frame/phase identify an event even if the observer repeats it.
  uint32_t kind,frame,phase;
  memcpy(&kind,(const char *)record-0x14,4);
  memcpy(&frame,(const char *)record-0x10,4);
  memcpy(&phase,(const char *)record-4,4);
  if (kind!=0x24 || phase>7) return;
  const uint64_t key=(((uint64_t)phase<<32)|frame)+1;
  if (__atomic_exchange_n(&referee_probe_event_key,key,__ATOMIC_ACQ_REL)==key) return;
  uint64_t previous=__atomic_load_n(&referee_probe_event,__ATOMIC_RELAXED),next;
  do {
    next=(((previous>>32)+1)<<32)|(reason<<8)|restart;
  } while (!__atomic_compare_exchange_n(&referee_probe_event,&previous,next,0,
                                        __ATOMIC_RELEASE,__ATOMIC_RELAXED));
  /* No filesystem work in this native match-event callback. */
}
static void referee_probe_suspend(int visible) {
  referee_perf_flush();
  __atomic_store_n(&referee_screen_sample,0,__ATOMIC_RELEASE);
  __atomic_store_n(&referee_world_tick,0,__ATOMIC_RELEASE);
  referee_player_snapshot_valid=0;
  referee_probe_set_display(visible && referee_probe_has_pose);
  // Replay/pause audio must not enqueue a delayed gesture on return to play.
  referee_probe_whistle_seen=__atomic_load_n(&referee_probe_whistle_serial,__ATOMIC_ACQUIRE);
  if (!referee_probe_tick && !referee_probe_live_frame) return;
  referee_probe_tick=0;
  referee_probe_live_frame=0;
  referee_motion_resume(&referee_motion);
  referee_probe_dt=0;
}
static void referee_probe_sound(const void *self,uint64_t handle,const uint8_t *command,
                                uint32_t arg,const void *registry,uint32_t player) {
  referee_sound_original(self,handle,command,arg,registry,player);
  // Audited PitchSound position command 0x4f / REFEREE_POS (0x1d), issued
  // after PlayMovement. No audio is replaced, delayed or played a second time.
  if (command && *command==0x4f && arg==0x1d && referee_probe_enabled &&
      !referee_probe_teardown && handle &&
      __atomic_exchange_n(&referee_probe_whistle_handle,handle,__ATOMIC_ACQ_REL)!=handle)
    __atomic_add_fetch(&referee_probe_whistle_serial,1,__ATOMIC_RELEASE);
}
static int referee_probe_follow(int scene) {
  const void *registry=referee_registry();
  if (!registry) return 0;
  const void *ball_info=NULL;
  // Same audited OpenRead BallInfo pointer used by the native-pad/HUD paths.
  memcpy(&ball_info,(const char *)registry+0x90,sizeof(ball_info));
  const float *trans=ball_info?referee_ball_trans(ball_info):NULL;
  if (!trans) return 0;
  const RefereePoint ball={trans[0],trans[2]};
  if (!referee_point_valid(ball)) return 0;
  const uint64_t now=armGetSystemTick();
  referee_using_demo=0;
  float dt=referee_probe_ready && referee_probe_tick && now>=referee_probe_tick?
      (float)((double)armTicksToNs(now-referee_probe_tick)*1.0e-9):0;
  referee_probe_tick=now;
  referee_probe_dt=fminf(0.1f,fmaxf(0,dt));
  const uint64_t event=__atomic_load_n(&referee_probe_event,__ATOMIC_ACQUIRE);
  if (referee_animation_bank.count>=8)
    referee_gesture_start(&referee_gesture,(uint32_t)(event>>32),(unsigned)(event&255),
                          (unsigned)((event>>8)&255));
  const int restart=scene==3?8:referee_probe_restart_active();
  const uint32_t whistle=__atomic_load_n(&referee_probe_whistle_serial,__ATOMIC_ACQUIRE);
  if (whistle!=referee_probe_whistle_seen) {
    referee_probe_whistle_seen=whistle;
    referee_gesture_whistle(&referee_gesture,(unsigned)restart);
    /* Counted in the deferred summary; synchronous SD writes here can stall
     * a native write frame on each whistle. */
  }
  if(referee_kickoff_ready) {
    const float distance_squared=ball.x*ball.x+ball.z*ball.z;
    if(distance_squared<=1.f)referee_kickoff_ready=2;
    else if(referee_kickoff_ready==2)referee_kickoff_ready=0;
    if(referee_kickoff_ready) {
      referee_motion_resume(&referee_motion);
      referee_player_snapshot_valid=0;
      return 1; // Keep the ready stance until the centre spot has been played.
    }
  }
  const uint32_t sequence=__atomic_load_n(&referee_demo_sequence,__ATOMIC_ACQUIRE);
  const uint64_t demo_tick=__atomic_load_n(&referee_demo_tick,__ATOMIC_ACQUIRE);
  const RefereePoint target={__atomic_load_n(&referee_demo_x,__ATOMIC_RELAXED)*.001f,
      __atomic_load_n(&referee_demo_z,__ATOMIC_RELAXED)*.001f};
  const float heading=__atomic_load_n(&referee_demo_heading,__ATOMIC_RELAXED)*.001f;
  __atomic_thread_fence(__ATOMIC_ACQUIRE);
  if(!(sequence&1u) && sequence==__atomic_load_n(&referee_demo_sequence,__ATOMIC_RELAXED) &&
      demo_tick && now>=demo_tick && armTicksToNs(now-demo_tick)<100000000ULL) {
    const float travel=hypotf(target.x-referee_motion.position.x,target.z-referee_motion.position.z);
    const float speed=referee_probe_dt>0 && travel<1.f ? travel/referee_probe_dt : 0;
    referee_motion_resume(&referee_motion);referee_motion.position=target;
    referee_motion.heading=heading;
    referee_using_demo=1;
    referee_motion.velocity=(RefereePoint){fminf(speed,3.f),0};
    referee_player_snapshot_valid=0;
    return 1;
  }
  // Only avoidance neighbours are sampled at 15 Hz. Ball, movement, gestures
  // and pose publication remain at native frame cadence. Store values, never
  // native pointers; invalidate on every suspension and stadium boundary.
  if (!referee_player_snapshot_valid || now<referee_player_snapshot_tick ||
      referee_elapsed_ns(referee_player_snapshot_tick,now)>=66666666ull) {
  referee_player_snapshot_count=0;
  for (uint32_t i=0;i<22;++i) {
    ++referee_perf.player_reads;
    const void *move=referee_player_move(registry,i);
    if (!move) continue;
    RefereeNativeVector p;
    memcpy(&p,(const char *)move+0x55c,sizeof(p));
    const RefereePoint point={p.x,p.z};
    if (referee_point_valid(point)) referee_player_snapshot[referee_player_snapshot_count++]=point;
  }
  referee_player_snapshot_tick=now;
  referee_player_snapshot_valid=1;
  }
  if (!referee_motion.initialized) referee_motion_reset(&referee_motion);
  if (dt>0) referee_motion_step_mode(&referee_motion,ball,referee_player_snapshot,
                                    referee_player_snapshot_count,dt,restart);
  return 1;
}
static int referee_probe_create_model(void *human, const RefereeProbeLoadId *load) {
  const int result=referee_create_model_original(human,load);
  if (!result || !referee_probe_enabled || referee_probe_teardown || !human) return result;
  uint32_t player;
  memcpy(&player, (const char *)human + 0x18, sizeof(player));
  if (player<22u && !referee_probe_model && !referee_probe_failed)
    referee_probe_pending=1;
  return result;
}

static int referee_probe_all_loaded(void *manager) {
  // HumanList::CreateSomething dirties the shared uniform manager. Enqueue
  // the extra model in the native loading transaction, never from Player::Draw.
  // First drain native player loads before adding an optional Human. Inserting
  // it while player/uniform jobs are in flight also mutates shared load lists.
  // IsAllLoaded must still be called during that interval to progress jobs.
  const int players_loaded=referee_all_loaded_original(manager);
  if (!players_loaded && !referee_probe_model) return 0;
  if (!referee_probe_model && referee_probe_pending &&
      __atomic_load_n(&referee_probe_scene_ready,__ATOMIC_ACQUIRE) && referee_uniform_busy()) {
    const uint64_t now=armGetSystemTick();
    if (!referee_probe_load_tick) referee_probe_load_tick=now;
    if (now<referee_probe_load_tick || armTicksToNs(now-referee_probe_load_tick)<=20000000000ull)
      return 0;
    referee_probe_pending=0;referee_probe_failed=1;
    referee_probe_note("Referee v11 uniform preflight timeout; native match continues.");
  }
  if (referee_probe_enabled && referee_probe_pending && !referee_probe_teardown &&
      __atomic_load_n(&referee_probe_scene_ready,__ATOMIC_ACQUIRE) &&
      !referee_probe_failed && !referee_probe_loaded) {
    if (!referee_probe_model) {
      void *match=exhibition_get_tmpdb_match();
      if (match) {
        uint32_t id=referee_get_id(match,0);
        if (!id) id=1;
        const NxMatchEnvironment env=nx_match_environment(pes_controller_stadium_weather(),
                                                         pes_controller_stadium_season(),1,1);
        const RefereeProbeLoadId load=referee_create_id(0,id,env.weather,env.season);
        referee_probe_model=referee_new(0x448);
        if (!referee_probe_model) referee_probe_failed=1;
        else {
          referee_ctor(referee_probe_model,2,&load);
          referee_set_lod(referee_probe_model,2,0,0); // Native match model policy.
          referee_probe_load_tick=armGetSystemTick();
          referee_probe_note("Referee v11 queued after native player and uniform loads drained.");
        }
      }
    }
    if (referee_probe_model) {
      referee_probe_loaded=referee_init(referee_probe_model)!=0;
      referee_probe_set_display(0);
      const uint64_t now=armGetSystemTick();
      if (!referee_probe_loaded && now>=referee_probe_load_tick &&
          armTicksToNs(now-referee_probe_load_tick)>20000000000ull) {
        referee_probe_clear();referee_probe_failed=1;
        referee_probe_note("Referee v11 preload timeout; match continues without the optional model.");
      }
    }
  }
  // The optional enqueue can invalidate the earlier readiness result.
  const int loaded=referee_probe_model?referee_all_loaded_original(manager):players_loaded;
  if (!loaded) return 0;
  // UE's LoadedCall marks the stock stadium loaded before our shell finishes.
  // The Fox loading thread must not advance through that intervening window.
  // Preview barriers before LoadedCall begins still return native readiness.
  if (referee_probe_enabled && __atomic_load_n(&referee_probe_scene_loading,__ATOMIC_ACQUIRE)) return 0;
  if (referee_probe_model && referee_uniform_busy()) {
    const uint64_t now=armGetSystemTick();
    if (now>=referee_probe_load_tick && armTicksToNs(now-referee_probe_load_tick)>20000000000ull) {
      referee_probe_clear();referee_probe_failed=1;
      referee_probe_note("Referee v11 uniform barrier timeout; optional model disabled.");
    } else return 0;
  }
  if (referee_probe_model && referee_probe_loaded && referee_probe_pending) {
    referee_probe_pending=0;
    referee_probe_note("Referee v11 native loading barrier complete; first pose may now publish.");
  }
  return !(referee_probe_model && !referee_probe_loaded && !referee_probe_failed);
}

static void referee_probe_draw(void *objects) {
  // The native ExecDrawListener completes its entire object list first. Do not
  // interleave loads or pose publication with any individual player's draw.
  referee_draw_original(objects);
  if (!referee_probe_enabled || referee_probe_failed || referee_probe_teardown ||
      !__atomic_load_n(&referee_probe_scene_ready,__ATOMIC_ACQUIRE) ||
      !referee_probe_model || !referee_probe_loaded || referee_probe_pending) return;
  referee_probe_hidden_kickoff();
  // Replay and paused menus hold the current pose. A goal scene keeps the
  // referee moving back toward halfway; returning from pause starts at dt=0.
  // The HUD's 80 ms freshness gate is for input, not model visibility. Read
  // the native match phase and explicit pause/replay owners instead.
  const int scene=referee_probe_scene_active(); // 0 hidden, 1 pause/replay, 2 live, 3 goal.
  if (scene!=2 && scene!=3) { referee_probe_suspend(scene==1); return; }
  // A repeated listener callback in the same upload frame cannot advance twice.
  const uint64_t stamp=referee_frame_stamp();
  const int new_frame=!referee_probe_frame || stamp!=referee_probe_stamp;
  const uint64_t perf_start=armGetSystemTick();
  if (new_frame) {
    referee_probe_stamp=stamp;
    ++referee_probe_frame;
    if (!referee_probe_follow(scene)) { referee_probe_suspend(1); return; }
    referee_probe_live_frame=1;
  }
  if (!referee_probe_live_frame || !new_frame) return;
  const uint64_t perf_follow=armGetSystemTick();
  const uint64_t point=(uint32_t)(int32_t)lrintf(referee_motion.position.x*1000.f) |
      ((uint64_t)(uint32_t)(int32_t)lrintf(referee_motion.position.z*1000.f)<<32);
  __atomic_store_n(&referee_world_point,point,__ATOMIC_RELAXED);
  __atomic_store_n(&referee_world_tick,perf_follow,__ATOMIC_RELEASE);
  if(referee_probe_offscreen(scene,perf_follow)) {
    /* Keep ball tracking and position current, but don't skin/publish a human
     * outside the padded camera. Re-entry publishes a complete fresh pose
     * BEFORE SetDisp(true); no rate reduction while the referee is visible. */
    referee_probe_set_display(0);
    ++referee_perf.culled;
    referee_perf_record(perf_start,perf_follow,perf_follow,perf_follow,armGetSystemTick());
    return;
  }
  void *vision = *(void **)((char *)referee_probe_model + 0x440);
  void *bone_buffer = *(void **)((char *)referee_probe_model + 0x418);
  if (!vision || !bone_buffer) {
    referee_probe_set_display(0);
    return;
  }
  const uintptr_t end=(uintptr_t)*(void **)((char *)referee_probe_model+0x420);
  if (end!=(uintptr_t)bone_buffer+20u*sizeof(RefereeBonePose)) {
    referee_probe_suspend(0);referee_probe_failed=1;
    referee_probe_note("Referee v11 bone-buffer contract mismatch; disabled.");
    return;
  }
  const float speed=hypotf(referee_motion.velocity.x,referee_motion.velocity.z);
  _Alignas(16) RefereeBonePose pose[REFEREE_ANIMATION_BONES];
  if (!referee_animation_step(&referee_animation_bank,&referee_animation_clock,
                              speed,referee_probe_dt,pose)) {
    referee_probe_suspend(1);return;
  }
  referee_gesture_apply(&referee_animation_bank,&referee_gesture,referee_probe_dt,pose);
  if (!referee_probe_ready) {
    const float scale=referee_root_scale((const char *)referee_probe_model+0x10);
    if (!isfinite(scale) || scale<0.25f || scale>4.0f) {
      referee_probe_suspend(0);referee_probe_failed=1;
      referee_probe_note("Referee v11 invalid model scale; disabled.");return;
    }
    const float inverse=1.0f/scale;
    memcpy((char *)referee_probe_model+0x438,&inverse,sizeof(inverse));
  }
  memcpy(bone_buffer,pose,sizeof(pose));
  // The native publisher copies all 20 entries although the body consumes 19.
  // Initialize its spare slot too; never send allocator contents to rendering.
  const RefereeBonePose spare={{0,0,0,1},{0,0,0,1}};
  memcpy((char *)bone_buffer+sizeof(pose),&spare,sizeof(spare));
  const uint64_t perf_pose=armGetSystemTick();
  referee_publish_bones(vision,(const char *)referee_probe_model+0x410);
  const uint64_t perf_publish=armGetSystemTick();
  referee_probe_has_pose=1;
  const _Alignas(16) RefereeProbeVector position = {
      referee_motion.position.x,0,referee_motion.position.z,0};
  const _Alignas(16) RefereeProbeVector offset = {0};
  if (new_frame || !referee_probe_ready)
    referee_update(referee_probe_model,&position,referee_motion.heading,&offset);
  referee_probe_set_display(referee_probe_has_pose);
  const uint64_t perf_end=armGetSystemTick();
  referee_perf_record(perf_start,perf_follow,perf_pose,perf_publish,perf_end);
  if (!referee_probe_ready) {
    referee_probe_ready = 1;
    referee_probe_note(referee_animation_bank.count>=8 ?
        "Referee v11 ready; EF10 upper-body gestures + native whistle timing; stadium-owned model." :
        "Referee v11 ready; old locomotion-only bank. Update FootballNX.assets for gestures.");
  }
  if (!referee_probe_moved && referee_motion.distance>=3.0f) {
    referee_probe_moved=1;
    referee_probe_note("Referee follower v11 has travelled >3m in live play. Visual only; native match decisions unchanged.");
  }
}

#ifndef PESNX_REFEREE_PROBE_HOST_TEST
static void install_referee_probe(so_module *module) {
  FILE *file = fopen("referee-probe.txt", "rb");
  if (!file) return;
  char token[25] = {0};
  size_t length = fread(token, 1, sizeof(token) - 1, file);
  fclose(file);
  if (length < 22 || memcmp(token, "PESNX_REFEREE_PROBE_V1", 22)) return;
  const char *create_symbol =
      "_ZN5match5Human11CreateModelERKN4draw4load11HumanLoadIdE";
  if (!so_try_find_addr_rx(module, create_symbol)) return;
  // RX is not mapped until so_finalize, after this installer returns.
  const uintptr_t create_model = so_find_addr(module, create_symbol);
  if (*(const uint32_t *)(create_model + 164) != 0x52808900)
    return;
  const char *observer_symbol="_ZN5match6record17ObserverOutOfPlay4ExecERNS_8registry11RecordEventERKNS0_13ObserverInputE";
  if (!so_try_find_addr_rx(module,observer_symbol)) return;
  const uintptr_t observer=so_find_addr(module,observer_symbol);
  if (*(const uint32_t *)(observer+0x64)!=0x52800481 ||
      *(const uint32_t *)(observer+0x80)!=0x91005280) return;
  const char *demo_symbol="_ZN11FixDemoMain20GetUpdateHumanPosRotERN4math7Vector3ERNS0_10QuaternionEjhhff";
  const char *fade_symbol="_ZNK5match8registry9MatchInfo12GetIsFadeOutEv";
  if(!so_try_find_addr_rx(module,demo_symbol) || !so_try_find_addr_rx(module,fade_symbol))return;
  const uintptr_t demo=so_find_addr(module,demo_symbol),fade=so_find_addr(module,fade_symbol);
  if(*(const uint32_t *)(demo+0x7c)!=0xf94676ea ||
      *(const uint32_t *)(demo+0x80)!=0xf94672e8 ||
      *(const uint32_t *)fade!=0x5282ed08 ||
      *(const uint32_t *)(fade+4)!=0x38686800)return;
  const uintptr_t draw_plt = (uintptr_t)module->load_base + 0x38a0b50;
  const uintptr_t create_plt = (uintptr_t)module->load_base + 0x38948e0;
  const uintptr_t loaded_plt = (uintptr_t)module->load_base + 0x3804970;
  const uintptr_t release_plt = (uintptr_t)module->load_base + 0x3812630;
  const uintptr_t unload_plt = (uintptr_t)module->load_base + 0x38dd250;
  const uintptr_t animation_release_plt = (uintptr_t)module->load_base + 0x3811040;
  const uintptr_t manager_create_plt = (uintptr_t)module->load_base + 0x3894b10;
  const uintptr_t destroy_loader_plt = (uintptr_t)module->load_base + 0x38cf4a0;
  const uintptr_t scene_loaded_plt = (uintptr_t)module->load_base + 0x38c3dc0;
  const uintptr_t out_plt = (uintptr_t)module->load_base + 0x37ed030;
  const uintptr_t sound_plt = (uintptr_t)module->load_base + 0x381c230;
  const uintptr_t flow_plt = (uintptr_t)module->load_base + 0x3887240;
  const uintptr_t demo_plt = (uintptr_t)module->load_base + 0x3845dd0;
  const uint32_t draw_words[] = {0xd002e370,0xf9440211,0x91200210,0xd61f0220};
  const uint32_t create_words[] = {0x9002e3b0,0xf9436611,0x911b2210,0xd61f0220};
  const uint32_t loaded_words[] = {0x9002e5f0,0xf9438a11,0x911c4210,0xd61f0220};
  const uint32_t release_words[] = {0xb002e5b0,0xf942ba11,0x9115c210,0xd61f0220};
  const uint32_t unload_words[] = {0xf002e270,0xf945c211,0x912e0210,0xd61f0220};
  const uint32_t animation_words[] = {0xb002e5b0,0xf9453e11,0x9129e210,0xd61f0220};
  const uint32_t manager_words[] = {0x9002e3b0,0xf943f211,0x911f8210,0xd61f0220};
  const uint32_t destroy_loader_words[] = {0xd002e2b0,0xf9465611,0x9132a210,0xd61f0220};
  const uint32_t scene_loaded_words[] = {0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220};
  const uint32_t out_words[] = {0xf002e630,0xf9453a11,0x9129c210,0xd61f0220};
  const uint32_t sound_words[] = {0x9002e590,0xf941ba11,0x910dc210,0xd61f0220};
  const uint32_t flow_words[] = {0xd002e3d0,0xf945be11,0x912de210,0xd61f0220};
  const uint32_t demo_words[] = {0x9002e4f0,0xf940a211,0x91050210,0xd61f0220};
  if (memcmp((void *)draw_plt, draw_words, 16) ||
      memcmp((void *)create_plt, create_words, 16) ||
      memcmp((void *)loaded_plt, loaded_words, 16) ||
      memcmp((void *)release_plt, release_words, 16) ||
      memcmp((void *)unload_plt, unload_words, 16) ||
      memcmp((void *)animation_release_plt, animation_words, 16) ||
      memcmp((void *)manager_create_plt, manager_words, 16) ||
      memcmp((void *)destroy_loader_plt, destroy_loader_words, 16) ||
      (!stadium_canary_installed && memcmp((void *)scene_loaded_plt, scene_loaded_words, 16)) ||
      memcmp((void *)out_plt, out_words, 16) ||
      memcmp((void *)sound_plt, sound_words, 16) ||
      memcmp((void *)flow_plt, flow_words, 16) ||
      memcmp((void *)demo_plt, demo_words, 16)) return;
#define REFEREE_BIND(target, symbol) do { \
  target = (void *)so_try_find_addr_rx(module, symbol); \
  if (!target) return; \
} while (0)
  REFEREE_BIND(referee_create_id, "_ZN4draw12CreateLoadIdE11RefereeKindjN6common11WeatherTypeENS1_10SeasonTypeE");
  REFEREE_BIND(referee_get_id, "_ZNK5tmpdb5Match12GetRefereeIdEj");
  REFEREE_BIND(referee_new, "_Znwm");
  REFEREE_BIND(referee_ctor, "_ZN4draw5HumanC2E9HumanKindRKNS_4load11HumanLoadIdE");
  REFEREE_BIND(referee_delete, "_ZN4draw5HumanD0Ev");
  REFEREE_BIND(referee_init, "_ZN4draw5Human4InitEv");
  REFEREE_BIND(referee_root_scale, "_ZNK5cobra3cfg19CharacterProportion12GetRootScaleEv");
  REFEREE_BIND(referee_update, "_ZN4draw5Human6UpdateERKN10Vectormath3Aos7Vector3EfS5_");
  REFEREE_BIND(referee_display, "_ZN4draw5Human7SetDispEb");
  REFEREE_BIND(referee_draw_original, "_ZN12match_system10ObjectList4DrawEv");
  REFEREE_BIND(referee_create_model_original, "_ZN5match5Human11CreateModelERKN4draw4load11HumanLoadIdE");
  REFEREE_BIND(referee_all_loaded_original, "_ZN4draw4load7Manager11IsAllLoadedEv");
  REFEREE_BIND(referee_uniform_busy, "_ZN6render14UniformManager6IsBusyEv");
  REFEREE_BIND(referee_set_lod, "_ZN4draw5Human6SetLodEN5cobra2rc5scene5LevelEff");
  REFEREE_BIND(referee_release_original, "_ZN4draw4load16HumanLoadManager7ReleaseEv");
  REFEREE_BIND(referee_unload_original, "_ZN14AStadiumLoader6UnLoadEv");
  REFEREE_BIND(referee_destroy_loader_original, "_ZN14AStadiumLoader13DestroyLoaderEv");
  REFEREE_BIND(referee_loaded_original, "_ZN14AStadiumLoader10LoadedCallEv");
  REFEREE_BIND(referee_out_original, "_ZN5match8registry15RecordOutOfPlay3SetEPKNS0_8RegistryERKNS0_14JudgeOutOfPlayE");
  REFEREE_BIND(referee_sound_original, "_ZNK5sound3app2ai10PitchSound11ExecCommandEyRKhNS0_11ai_selector12SysParamData14CommandArgTypeEPKN5match8registry8RegistryE8PlayerNo");
  REFEREE_BIND(referee_animation_release_original, "_ZN4draw5anime15ResourceManager7ReleaseEv");
  REFEREE_BIND(referee_manager_create_original, "_ZN4draw4load7Manager6CreateEv");
  REFEREE_BIND(referee_publish_bones, "_ZN18VisionModelManager11VisionModel12SetBodyBonesEPN5cobra2rc5scene22CharacterBonesRotTransE");
  REFEREE_BIND(referee_registry, "_ZN5match8registry14GlobalRegistry19GetInstanceForRetryEv");
  REFEREE_BIND(referee_player_move, "_ZNK5match8registry14GlobalRegistry13GetPlayerMoveE8PlayerNo");
  REFEREE_BIND(referee_ball_trans, "_ZNK5match8registry8BallInfo8GetTransEv");
  REFEREE_BIND(referee_frame_stamp, "_ZN5cobra2rs5Async9FramePool17GetWriteTimestampEv");
  REFEREE_BIND(referee_reset_flow_original, "_ZN5match4Flow9ResetFlowENS_8FlowKindE");
  REFEREE_BIND(referee_demo_transform_original, "_ZN11FixDemoMain20GetUpdateHumanPosRotERN4math7Vector3ERNS0_10QuaternionEjhhff");
  REFEREE_BIND(referee_match_faded, "_ZNK5match8registry9MatchInfo12GetIsFadeOutEv");
#undef REFEREE_BIND
  if (stadium_canary_installed) referee_loaded_original=stadium_loaded_canary;
  size_t animation_size=0;
  referee_animation_data=nx_asset_read("Animations/referee.nxra",REFEREE_ANIMATION_LIMIT,&animation_size);
  if (!referee_animation_bind(&referee_animation_bank,referee_animation_data,animation_size)) {
    free(referee_animation_data);referee_animation_data=NULL;
    referee_probe_note("Referee v11 requires valid EF10 clips in FootballNX.assets; disabled.");
    return;
  }
  hook_arm64(draw_plt, (uintptr_t)referee_probe_draw);
  hook_arm64(create_plt, (uintptr_t)referee_probe_create_model);
  hook_arm64(loaded_plt, (uintptr_t)referee_probe_all_loaded);
  hook_arm64(release_plt, (uintptr_t)referee_probe_release);
  hook_arm64(unload_plt, (uintptr_t)referee_probe_unload);
  hook_arm64(animation_release_plt, (uintptr_t)referee_probe_animation_release);
  hook_arm64(manager_create_plt, (uintptr_t)referee_probe_manager_create);
  hook_arm64(destroy_loader_plt, (uintptr_t)referee_probe_destroy_loader);
  hook_arm64(scene_loaded_plt, (uintptr_t)referee_probe_loaded_scene);
  hook_arm64(out_plt, (uintptr_t)referee_probe_out_of_play);
  hook_arm64(sound_plt, (uintptr_t)referee_probe_sound);
  hook_arm64(flow_plt, (uintptr_t)referee_probe_reset_flow);
  hook_arm64(demo_plt, (uintptr_t)referee_probe_demo_transform);
  referee_probe_enabled = 1;
  referee_probe_note("Referee follower v17 armed; padded native-camera culling, full-rate visible pose, deferred CPU summaries.");
}
#endif
