/* Presentation-only adapter: the existing offline Game Plan renderer reads
 * the server draft through these accessors. It never writes engine squads.
 * All non-manager calls continue to the original native getters. */
#define PESNX_MANAGER_RENDER_ADAPTER 1
static MdView manager_render_plan;
static int manager_render_plan_active;
static void manager_render_plan_snapshot(int visible) {
  manager_render_plan_active=0;
  if(!visible)return;
  manager_client_view(&manager_render_plan);
  manager_render_plan_active=(manager_render_plan.page==MD_CLUB_PLAN||manager_render_plan.page==MD_PLAN_SETTINGS);
  if(manager_render_plan_active&&!manager_render_plan.online){
    static const float x[]={.5f,.14f,.38f,.62f,.86f,.23f,.5f,.77f,.18f,.5f,.82f};
    static const float y[]={.84f,.64f,.64f,.64f,.64f,.43f,.43f,.43f,.17f,.17f,.17f};
    for(unsigned i=0;i<11;i++){manager_render_plan.plan_dots[i].x=x[i];manager_render_plan.plan_dots[i].y=y[i];}
  }
}
static uint32_t manager_render_plan_count(void) {
  unsigned count=manager_render_plan.plan_count;
  return count>=18&&count<=MD_PLAN_PLAYERS?count:18u;
}
static uint32_t manager_render_plan_root(void) {return manager_render_plan.online?MD_PLAN_PLAYERS:18u;}
static uint32_t manager_render_plan_bench_focus(void) {
  unsigned focus=manager_render_plan.focus;
  if(focus>=11&&focus<manager_render_plan_count())return focus-11;
  focus=manager_render_plan.plan_bench_focus;
  return focus<manager_render_plan_count()-11?focus:0;
}
static const MdPlanPlayer *manager_render_plan_player(uint32_t starting,uint32_t index) {
  static const MdPlanPlayer empty={0};
  if(index>=(starting?11u:manager_render_plan_count()-11))return &empty;
  return &manager_render_plan.plan_players[(starting?0:11)+index];
}
static const char *manager_render_plan_role(unsigned role) {
  static const char *const names[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};return role<13?names[role]:"";
}
static void manager_render_plan_queue_portraits(void) {
  if(!manager_render_plan_active)return;
  /* Hold a batch for the async game-thread loader. Missing PNGs cannot keep
   * the same five players ahead of every other portrait indefinitely. */
  unsigned bench=manager_render_plan_count()-11,visible=bench>7?7:bench,focus=manager_render_plan_bench_focus();
  unsigned start=focus>visible/2?focus-visible/2:0;if(start+visible>bench)start=bench-visible;
  unsigned total=11+visible,requested=0,first=(unsigned)(manager_render_plan.now_ms/250u)*5u%total;
  for(unsigned i=0;i<total&&requested<5;i++) {
    unsigned at=(first+i)%total;
    uint32_t id=manager_render_plan.plan_players[at<11?at:at+start].portrait;
    if(id&&!gameplan_portrait_texture(id))pes_controller_league_request_scorer_portrait(requested++,id);
  }
}
static uint32_t manager_render_page(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.page==MD_PLAN_SETTINGS?PES_PREMATCH_GAMEPLAN_PAGE_FORMATION:manager_render_plan.plan_editable&&manager_render_plan.focus<manager_render_plan_count()?PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE:PES_PREMATCH_GAMEPLAN_PAGE_ROOT;return pes_controller_custom_prematch_gameplan_page(pad);}
#define pes_controller_custom_prematch_gameplan_page manager_render_page
static uint32_t manager_render_root_focus(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.plan_editable&&manager_render_plan.page==MD_CLUB_PLAN&&manager_render_plan.focus>=manager_render_plan_root()&&manager_render_plan.focus<manager_render_plan_root()+4?manager_render_plan.focus-manager_render_plan_root():0u;return pes_controller_custom_prematch_gameplan_root_focus(pad);}
#define pes_controller_custom_prematch_gameplan_root_focus manager_render_root_focus
static uint32_t manager_render_field_count(uint32_t pad) {if(manager_render_plan_active)return 11u;return pes_controller_custom_prematch_gameplan_field_count(pad);}
#define pes_controller_custom_prematch_gameplan_field_count manager_render_field_count
static uint32_t manager_render_bench_count(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan_count()-11;return pes_controller_custom_prematch_gameplan_bench_count(pad);}
#define pes_controller_custom_prematch_gameplan_bench_count manager_render_bench_count
static int manager_render_waiting(uint32_t pad) {if(manager_render_plan_active)return 0;return pes_controller_custom_prematch_gameplan_waiting(pad);}
#define pes_controller_custom_prematch_gameplan_waiting manager_render_waiting
static int manager_render_condition_mode(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.plan_condition;return pes_controller_custom_prematch_gameplan_condition_mode(pad);}
#define pes_controller_custom_prematch_gameplan_condition_mode manager_render_condition_mode
static uint32_t manager_render_player_condition(uint32_t pad,uint32_t starting,uint32_t index) {if(manager_render_plan_active)return 2u;return pes_controller_custom_prematch_gameplan_player_condition(pad,starting,index);}
#define pes_controller_custom_prematch_gameplan_player_condition manager_render_player_condition
static const char * manager_render_player_name(uint32_t pad,uint32_t starting,uint32_t index) {if(manager_render_plan_active)return manager_render_plan_player(starting,index)->label;return pes_controller_custom_prematch_gameplan_player_name(pad,starting,index);}
#define pes_controller_custom_prematch_gameplan_player_name manager_render_player_name
static const char * manager_render_player_role(uint32_t pad,uint32_t starting,uint32_t index) {if(manager_render_plan_active)return manager_render_plan_role(manager_render_plan_player(starting,index)->role);return pes_controller_custom_prematch_gameplan_player_role(pad,starting,index);}
#define pes_controller_custom_prematch_gameplan_player_role manager_render_player_role
static uint32_t manager_render_player_overall(uint32_t pad,uint32_t starting,uint32_t index) {if(manager_render_plan_active)return manager_render_plan_player(starting,index)->rating;return pes_controller_custom_prematch_gameplan_player_overall(pad,starting,index);}
#define pes_controller_custom_prematch_gameplan_player_overall manager_render_player_overall
static uint32_t manager_render_player_portrait_id(uint32_t pad,uint32_t starting,uint32_t index) {if(manager_render_plan_active)return manager_render_plan_player(starting,index)->portrait;return pes_controller_custom_prematch_gameplan_player_portrait_id(pad,starting,index);}
#define pes_controller_custom_prematch_gameplan_player_portrait_id manager_render_player_portrait_id
static uint32_t manager_render_player_pitch_x(uint32_t pad,uint32_t index) {if(manager_render_plan_active)return index<11?(uint32_t)(manager_render_plan.plan_dots[index].x*255.f+.5f):0u;return pes_controller_custom_prematch_gameplan_player_pitch_x(pad,index);}
#define pes_controller_custom_prematch_gameplan_player_pitch_x manager_render_player_pitch_x
static uint32_t manager_render_player_pitch_y(uint32_t pad,uint32_t index) {if(manager_render_plan_active)return index<11?(uint32_t)(manager_render_plan.plan_dots[index].y*255.f+.5f):0u;return pes_controller_custom_prematch_gameplan_player_pitch_y(pad,index);}
#define pes_controller_custom_prematch_gameplan_player_pitch_y manager_render_player_pitch_y
static uint32_t manager_render_substitute_area(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.focus<11?0u:1u;return pes_controller_custom_prematch_gameplan_substitute_area(pad);}
#define pes_controller_custom_prematch_gameplan_substitute_area manager_render_substitute_area
static uint32_t manager_render_substitute_focus(uint32_t pad,uint32_t area) {if(manager_render_plan_active)return manager_render_plan.plan_editable?(area==0?(manager_render_plan.focus<11?manager_render_plan.focus:manager_render_plan.plan_field_focus):manager_render_plan_bench_focus()):UINT32_MAX;return pes_controller_custom_prematch_gameplan_substitute_focus(pad,area);}
#define pes_controller_custom_prematch_gameplan_substitute_focus manager_render_substitute_focus
static uint32_t manager_render_drag_state(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.plan_move;return pes_controller_custom_prematch_gameplan_drag_state(pad);}
#define pes_controller_custom_prematch_gameplan_drag_state manager_render_drag_state
static int manager_render_substitute_selected(uint32_t pad,uint32_t area,uint32_t index) {if(manager_render_plan_active)return manager_render_plan.plan_editable&&manager_render_plan.plan_pick==(area?11u:0u)+index;return pes_controller_custom_prematch_gameplan_substitute_selected(pad,area,index);}
#define pes_controller_custom_prematch_gameplan_substitute_selected manager_render_substitute_selected
static const char * manager_render_formation_label(uint32_t pad) {if(manager_render_plan_active)return manager_render_plan.plan_formation;return pes_controller_custom_prematch_gameplan_formation_label(pad);}
#define pes_controller_custom_prematch_gameplan_formation_label manager_render_formation_label
