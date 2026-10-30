/* Own-club editor. Draft changes are local; only a dirty leave sends a PUT. */

static const char *const mo_tactic_keys[]={"mentality","tempo","pressing","defensive_line"};
static const char *const mo_tactics[4][3]={{"DEFENSIVE","NORMAL","ATTACKING"},{"SLOW","NORMAL","FAST"},{"LOW","MID","HIGH"},{"LOW","MID","HIGH"}};
static const char *const mo_duty_keys[]={"captain_id","corner_right","corner_left","free_kick_long","free_kick_short","penalty_taker","set_piece_attacker_1","set_piece_attacker_2","set_piece_attacker_3"};
static int plan_decode(const MjDoc *d,int object,MoPlan *out){
  MoPlan p={0};char formation[16];int xi=mj_get(d,object,"xi"),bench=mj_get(d,object,"bench"),tactics=mj_get(d,object,"tactics");
  if(!field_text(d,object,"formation",formation,sizeof(formation)))return 0;
  for(p.formation=0;p.formation<FNX_GAMEPLAN_SHAPE_COUNT&&strcmp(formation,fnx_gameplan_shapes[p.formation].label);p.formation++);
  if(p.formation==FNX_GAMEPLAN_SHAPE_COUNT||!mj_is(d,xi,MJ_ARRAY)||d->tokens[xi].count!=11||!mj_is(d,bench,MJ_ARRAY)||d->tokens[bench].count!=7)return 0;
  for(unsigned i=0;i<4;i++){char value[16];p.tactics[i]=1;
    if(field_text(d,tactics,mo_tactic_keys[i],value,sizeof(value))){for(p.tactics[i]=0;p.tactics[i]<3&&strcmp(value,mo_tactics[i][p.tactics[i]]);p.tactics[i]++);if(p.tactics[i]==3)return 0;}}
  p.offside=field_bool(d,tactics,"auto_offside_trap");p.auto_subs=mj_get(d,tactics,"auto_substitutions")<0?1:field_bool(d,tactics,"auto_substitutions");
  for(unsigned i=0;i<18;i++){
    int entry=mj_at(d,i<11?xi:bench,(int)(i<11?i:i-11));p.ids[i]=field_u64(d,entry,"instance_id");
    if(!find_instance(p.ids[i]))return 0;
    for(unsigned j=0;j<i;j++)if(p.ids[j]==p.ids[i])return 0;
    if(i<11){char assigned[16];
      if(!required_u32(d,entry,"x",&p.x[i])||!required_u32(d,entry,"y",&p.y[i])||p.x[i]>105000||p.y[i]>68000||!field_text(d,entry,"role",assigned,sizeof(assigned)))return 0;
      p.roles[i]=role(assigned);if(p.roles[i]>=13)return 0;}
  }
  for(unsigned i=0;i<9;i++){p.duties[i]=field_u64(d,object,mo_duty_keys[i]);if(p.duties[i]){unsigned j=0;while(j<11&&p.ids[j]!=p.duties[i])j++;if(j==11)return 0;}}
  *out=p;return 1;
}
static void plan_display(void){
  /* The saved eighteen lead the editor roster. Every other owned player is
   * available in the same scrolling list, without entering another screen. */
  uint64_t roster[MO_PLAYERS]={0};unsigned count=18;
  memcpy(roster,online.plan.ids,sizeof(online.plan.ids));
  for(unsigned pass=0;pass<2;pass++)for(unsigned i=pass?0:18;i<(pass?online.player_count:online.plan_count);i++){
    uint64_t id=pass?online.players[i].instance:online.plan_roster[i];
    unsigned j=0;while(j<count&&roster[j]!=id)j++;
    if(j==count&&count<MO_PLAYERS&&find_instance(id))roster[count++]=id;
  }
  memcpy(online.plan_roster,roster,sizeof(roster));online.plan_count=count;
  memset(online.plan_players,0,sizeof(online.plan_players));
  for(unsigned i=0;i<count;i++){
    MoPlayer *p=find_instance(roster[i]);MdPlanPlayer *v=&online.plan_players[i];if(!p)continue;
    copy(v->label,sizeof(v->label),p->row.label);v->identity=p->row.identity;v->portrait=p->row.portrait;v->rating=p->row.rating;v->role=i<11?online.plan.roles[i]:p->row.role;
    if(i<11)online.plan_dots[i]=(MdDot){(float)online.plan.y[i]/68000.f,1.f-(float)online.plan.x[i]/105000.f,0,i+1};
  }
  online.plan_dirty=memcmp(&online.plan,&online.plan_saved,sizeof(MoPlan))!=0;
}
static int parse_plan(const MjDoc *d,int data){
  MoPlan p;uint32_t revision;int object=mj_get(d,data,"plan");
  if(!plan_decode(d,object,&p)||!required_u32(d,data,"revision",&revision)||!revision||!mj_copy(d,object,online.plan_json,sizeof(online.plan_json)))return 0;
  online.plan=online.plan_saved=p;online.plan_revision=revision;online.plan_focus=MO_PLAYERS;online.plan_picker=online.plan_menu_focus=online.plan_field_focus=online.plan_bench_focus=0;online.plan_pick=UINT32_MAX;
  online.plan_count=0;memset(online.plan_roster,0,sizeof(online.plan_roster));
  online.plan_buttons=online.plan_condition=0;online.plan_dirty=online.plan_move=online.plan_menu=online.plan_save_pending=online.plan_leave=online.plan_discard=0;online.plan_key[0]=0;
  plan_display();return 1;
}
static void plan_exit(void){
  online.plan_move=0;online.plan_pick=UINT32_MAX;
  route_back();
}
static int plan_encode(char *body,size_t capacity){
  const MoPlan *p=&online.plan;size_t used=0;int n;
#define PLAN_APPEND(...) do {n=snprintf(body+used,capacity-used,__VA_ARGS__);if(n<0||(size_t)n>=capacity-used)return 0;used+=(size_t)n;} while(0)
  PLAN_APPEND("{\"expected_revision\":%u,\"formation\":\"%s\",\"tactics\":{",online.plan_revision,fnx_gameplan_shapes[p->formation].label);
  for(unsigned i=0;i<4;i++)PLAN_APPEND("%s\"%s\":\"%s\"",i?",":"",mo_tactic_keys[i],mo_tactics[i][p->tactics[i]]);
  PLAN_APPEND(",\"auto_offside_trap\":%s,\"auto_substitutions\":%s},\"xi\":[",p->offside?"true":"false",p->auto_subs?"true":"false");
  for(unsigned i=0;i<18;i++){
    MoPlayer *player=find_instance(p->ids[i]);if(!player)return 0;
    if(i==11)PLAN_APPEND("],\"bench\":[");
    PLAN_APPEND("%s{\"instance_id\":%llu,\"player_key\":\"%s\",\"role\":\"%s\",\"x\":%u,\"y\":%u}",i&&i!=11?",":"",(unsigned long long)p->ids[i],player->key,role_names[i<11?p->roles[i]:player->row.role],i<11?p->x[i]:0,i<11?p->y[i]:0);
  }
  PLAN_APPEND("]");for(unsigned i=0;i<9;i++)if(p->duties[i])PLAN_APPEND(",\"%s\":%llu",mo_duty_keys[i],(unsigned long long)p->duties[i]);PLAN_APPEND("}");
#undef PLAN_APPEND
  return 1;
}
static void plan_save_leave(void){
  if(!online.plan_dirty){plan_exit();return;}
  if(!online.plan_save_pending&&!plan_encode(online.plan_body,sizeof(online.plan_body))){message("GAME PLAN","The draft is incomplete. Check your eleven and bench.");return;}
  online.plan_leave=1;
  if(request(J_SAVE_PLAN,"PUT","/club/gameplan",online.plan_body,1))online.plan_save_pending=1;
}
static int plan_verify(const MjDoc *d,int data){
  MoPlan saved;uint32_t revision;
  if(!plan_decode(d,mj_get(d,data,"plan"),&saved)||!required_u32(d,data,"revision",&revision)||!revision)return 0;
  if(!memcmp(&saved,&online.plan,sizeof(saved))){online.plan_saved=saved;online.plan_revision=revision;online.plan_dirty=online.plan_save_pending=0;online.plan_key[0]=0;if(online.plan_leave)plan_exit();}
  else {online.plan_leave=0;message("DRAFT KEPT","The server has a different Game Plan. B retries your saved request. X lets you discard the draft and reload the server plan.");}
  return 1;
}
static void plan_formation(unsigned formation){
  if(formation>=FNX_GAMEPLAN_SHAPE_COUNT)return;
  const FnxGameplanShape *shape=&fnx_gameplan_shapes[formation];MoPlan before=online.plan;unsigned used=0;
  for(unsigned i=0;i<11;i++){
    unsigned best=0;uint64_t cost=UINT64_MAX;
    for(unsigned j=0;j<11;j++)if(!(used&(1u<<j))){
      int dx=(int)(before.y[j]*255u/68000u)-(int)(shape->x[i]*255u/105u);
      int dy=(int)(before.x[j]*255u/105000u)-(int)(shape->y[i]*255u/48u);
      unsigned ar=before.roles[j],br=shape->role[i];
      unsigned al=ar==0?0:ar<=3?1:ar<=8?2:3,bl=br==0?0:br<=3?1:br<=8?2:3;
      uint64_t score=dx*dx+dy*dy+(ar!=br?200000u:0)+(al!=bl?400000u:0)+((ar==0)!=(i==0)?1000000u:0);
      if(score<cost){cost=score;best=j;}
    }
    used|=1u<<best;online.plan.ids[i]=before.ids[best];online.plan.roles[i]=shape->role[i];
    online.plan.x[i]=shape->y[i]*105000u/48u;online.plan.y[i]=shape->x[i]*68000u/105u;
  }
  online.plan.formation=formation;plan_display();
}
static void plan_move_focus(uint32_t key){
  unsigned slot=online.plan_focus;
  if(slot>=11){
    if(key&LEFT){online.plan_bench_focus=slot-11;online.plan_focus=online.plan_field_focus;}
    else {unsigned count=online.plan_count-11;online.plan_bench_focus=(slot-11+(key&UP?count-1:1))%count;online.plan_focus=11+online.plan_bench_focus;}
    return;
  }
  online.plan_field_focus=slot;unsigned best=UINT32_MAX;uint64_t cost=UINT64_MAX;
  for(unsigned i=0;i<11;i++)if(i!=slot){
    int dx=(int)(online.plan.y[i]*255u/68000u)-(int)(online.plan.y[slot]*255u/68000u);
    int dy=(int)(online.plan.x[slot]*255u/105000u)-(int)(online.plan.x[i]*255u/105000u);
    int f=key&LEFT?-dx:key&RIGHT?dx:key&UP?-dy:dy,lat=key&(LEFT|RIGHT)?dy:dx;
    if(f<=3||abs(lat)>f*3)continue;
    uint64_t score=f*f+lat*lat;
    if(score<cost){cost=score;best=i;}
  }
  if(best!=UINT32_MAX)online.plan_focus=online.plan_field_focus=best;
  else if(key&RIGHT)online.plan_focus=11+online.plan_bench_focus;
}

/* Match the offline role picker: all eleven for duties, NONE plus outfield
 * players for the three attacking set-piece slots. */
static uint64_t plan_picker_id(unsigned at){
  if(online.plan_menu_focus<6)return at<11?online.plan.ids[at]:0;
  if(!at)return 0;
  for(unsigned i=0;i<11;i++)if(online.plan.roles[i]&&!--at)return online.plan.ids[i];
  return 0;
}
static unsigned plan_picker_count(void){
  if(online.plan_menu_focus<6)return 11;
  unsigned count=1;for(unsigned i=0;i<11;i++)count+=online.plan.roles[i]!=0;return count;
}
static unsigned plan_reserves(unsigned *indices){
  unsigned count=0;
  for(unsigned i=0;i<online.player_count;i++){
    unsigned slot=0;while(slot<18&&online.plan.ids[slot]!=online.players[i].instance)slot++;
    if(slot==18)indices[count++]=i;
  }
  return count;
}

static void plan_pad(uint32_t key){
  if(online.page==MD_PLAN_RESERVES){
    unsigned indices[MO_PLAYERS],count=plan_reserves(indices),slot=online.plan_focus;
    if(key&B){change_page(MD_CLUB_PLAN);return;}
    if((key&UP)&&online.focus)online.focus--;
    else if((key&DOWN)&&online.focus+1<count)online.focus++;
    else if((key&A)&&online.focus<count&&slot<18){
      MoPlayer *p=&online.players[indices[online.focus]];
      if(slot<11&&((online.plan.roles[slot]==0)!=(p->row.role==0))){message("GOALKEEPER","Use a goalkeeper only in the starting goalkeeper position.");return;}
      uint64_t previous=online.plan.ids[slot];online.plan.ids[slot]=p->instance;
      if(slot<11)for(unsigned i=0;i<9;i++)if(online.plan.duties[i]==previous)online.plan.duties[i]=p->instance;
      online.plan_pick=UINT32_MAX;plan_display();change_page(MD_CLUB_PLAN);
    }
    return;
  }
  if(online.plan_discard){
    if(key&B)online.plan_discard=0;
    else if(key&(LEFT|RIGHT|UP|DOWN))online.focus^=1;
    else if(key&A){online.plan_discard=0;if(!online.focus){read_cache_drop(J_PLAN);get(J_PLAN,"/club/gameplan");}}
    return;
  }
  if(online.plan_save_pending){
    if(key&Y)get(J_PLAN_VERIFY,"/club/gameplan");else if(key&B)plan_save_leave();else if(key&X){online.plan_discard=1;online.focus=1;}return;
  }
  if(online.page==MD_PLAN_SETTINGS){
    unsigned count=online.plan_picker?(online.plan_menu==1?FNX_GAMEPLAN_SHAPE_COUNT+1:plan_picker_count()):online.plan_menu==3?9:4;
    if(key&B){if(online.plan_picker){online.plan_picker=0;online.focus=online.plan_menu_focus;}else{online.plan_focus=MO_PLAYERS+online.plan_menu;change_page(MD_CLUB_PLAN);}return;}
    if(online.plan_picker){
      if(key&(UP|LEFT))online.focus=(online.focus+count-1)%count;
      else if(key&(DOWN|RIGHT))online.focus=(online.focus+1)%count;
      else if(key&A){if(online.plan_menu==1){if(online.focus==FNX_GAMEPLAN_SHAPE_COUNT){plan_formation(online.plan_saved.formation);}else plan_formation(online.focus);}
        else {uint64_t id=plan_picker_id(online.focus);
          if(online.plan_menu_focus>=6&&id)for(unsigned i=6;i<9;i++)if(i!=online.plan_menu_focus&&online.plan.duties[i]==id)online.plan.duties[i]=0;
          online.plan.duties[online.plan_menu_focus]=id;plan_display();}
        online.plan_picker=0;online.focus=online.plan_menu_focus;
      }return;
    }
    if(key&UP)online.focus=(online.focus+count-1)%count;
    else if(key&DOWN)online.focus=(online.focus+1)%count;
    else if(key&(A|LEFT|RIGHT)){
      unsigned step=key&LEFT?2:1;
      if(online.plan_menu==1){
        if(online.focus==1){if(key&A){online.plan_menu_focus=online.focus;online.plan_picker=1;online.focus=online.plan.formation;}else plan_formation((online.plan.formation+(key&LEFT?FNX_GAMEPLAN_SHAPE_COUNT-1:1))%FNX_GAMEPLAN_SHAPE_COUNT);}
        else if(online.focus==0)online.plan.tactics[0]=(online.plan.tactics[0]+step)%3;
        else if(online.focus==2)online.plan.offside^=1;else online.plan.auto_subs^=1;
      }else if(online.plan_menu==2)online.plan.tactics[online.focus]=(online.plan.tactics[online.focus]+step)%3;
      else if(key&A){online.plan_menu_focus=online.focus;online.plan_picker=1;online.focus=0;for(unsigned i=0;i<plan_picker_count();i++)if(online.plan.duties[online.plan_menu_focus]==plan_picker_id(i))online.focus=i;}
      plan_display();
    }return;
  }
  unsigned slot=online.plan_focus;
  if((key&X)&&slot<18){online.plan_move=0;change_page(MD_PLAN_RESERVES);return;}
  if(key&R){online.plan_condition^=1;return;}
  if(key&B){if(online.plan_pick!=UINT32_MAX)online.plan_pick=UINT32_MAX;else if(slot<MO_PLAYERS)online.plan_focus=MO_PLAYERS;else plan_save_leave();return;}
  if((key&Y)&&slot<11){online.plan.roles[slot]=fnx_gameplan_zone_role(online.plan.roles[slot],online.plan.y[slot]*105u/68000u,online.plan.x[slot]*48u/105000u,1);plan_display();return;}
  if(key&A){
    if(slot>=MO_PLAYERS){if(slot==MO_PLAYERS){online.plan_focus=online.plan_field_focus;online.plan_pick=UINT32_MAX;}else {online.plan_menu=slot-MO_PLAYERS;online.plan_picker=0;change_page(MD_PLAN_SETTINGS);}return;}
    if(slot>=online.plan_count)return;
    if(online.plan_pick==UINT32_MAX){online.plan_pick=slot;return;}
    unsigned from=online.plan_pick;online.plan_pick=UINT32_MAX;if(from==slot)return;
    if(from>=online.plan_count)return;
    if(from>=18&&slot>=18){online.plan_pick=slot;return;}
    MoPlayer *a=find_instance(online.plan_roster[from]),*b=find_instance(online.plan_roster[slot]);
    if(!a||!b)return;
    if((from<11&&((online.plan.roles[from]==0)!=(b->row.role==0)))||(slot<11&&((online.plan.roles[slot]==0)!=(a->row.role==0)))){message("GOALKEEPER","Keep a goalkeeper in the starting goalkeeper position.");return;}
    uint64_t temp=online.plan_roster[from];online.plan_roster[from]=online.plan_roster[slot];online.plan_roster[slot]=temp;
    memcpy(online.plan.ids,online.plan_roster,sizeof(online.plan.ids));
    if((from<11)!=(slot<11)){uint64_t off=online.plan_roster[from<11?slot:from],on=online.plan_roster[from<11?from:slot];for(unsigned i=0;i<9;i++)if(online.plan.duties[i]==off)online.plan.duties[i]=on;}
    plan_display();return;
  }
  if(key&(LEFT|RIGHT|UP|DOWN)){
    if(slot>=MO_PLAYERS)online.plan_focus=MO_PLAYERS+(slot-MO_PLAYERS+(key&(LEFT|UP)?3:1))%4;
    else plan_move_focus(key);
  }
}

/* Consume every HID sample, including release and held frames. Menu navigation
 * still uses pressed/repeated edges; a field A press is owned by this gesture. */
static uint32_t plan_sample(uint32_t buttons,uint32_t key,int32_t ax,int32_t ay){
  const uint32_t pressed=buttons&~online.plan_buttons;
  online.plan_buttons=buttons;
  if(online.plan_focus>=11||online.page!=MD_CLUB_PLAN||online.plan_save_pending)return key;
  if((key&B)&&online.plan_move){online.plan_move=0;return 0;}
  if((pressed&A)&&!(buttons&B)&&!online.plan_move){
    unsigned slot=online.plan_focus;online.plan_move=2;online.plan_hold_at=online.plan_drag_at=online.mono;
    online.plan_drag_x=online.plan.y[slot]*255.f/68000.f;
    online.plan_drag_y=255.f-online.plan.x[slot]*255.f/105000.f;
  }
  if(online.plan_move==2&&(buttons&A)&&online.mono-online.plan_hold_at>=FNX_GAMEPLAN_HOLD_MS){
    online.plan_move=1;online.plan_drag_at=online.mono;online.plan_pick=UINT32_MAX;
  }
  if(online.plan_move==1&&(buttons&A)){
    unsigned slot=online.plan_focus;
    float dx=ax?(float)ax/32767.f:(float)(((buttons&RIGHT)!=0)-((buttons&LEFT)!=0));
    float dy=ay?(float)ay/32767.f:(float)(((buttons&DOWN)!=0)-((buttons&UP)!=0));
    /* Use the same direction as menu navigation. Cobra's existing direction
     * bits can coexist with an axis in the game's opposite Y convention. */
    if((buttons&(UP|DOWN))==UP)dy=-(dy<0?-dy:dy);
    else if((buttons&(UP|DOWN))==DOWN)dy=dy<0?-dy:dy;
    fnx_gameplan_drag(&online.plan_drag_x,&online.plan_drag_y,online.plan.roles[slot]==0,dx,dy,online.mono-online.plan_drag_at);
    online.plan_drag_at=online.mono;
    unsigned width=(unsigned)(online.plan_drag_x*105.f/255.f+.5f),depth=(unsigned)((255.f-online.plan_drag_y)*48.f/255.f+.5f);
    if(dx||dy){online.plan.y[slot]=width*68000u/105u;online.plan.x[slot]=depth*105000u/48u;
      online.plan.roles[slot]=fnx_gameplan_zone_role(online.plan.roles[slot],width,depth,0);plan_display();}
  }
  if(online.plan_move&&!(buttons&A)){
    unsigned tap=online.plan_move==2;online.plan_move=0;return tap?A:0;
  }
  return online.plan_move?0:key&~A;
}
