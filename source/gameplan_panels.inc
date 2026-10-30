/* Flat Matchday editor panels. Snapshot native values once; rendering cannot
 * change focus, assignments or save slots. Shares the menu font/art/draw path. */
typedef struct {
  char label[96], value[96], role[8];
  uint32_t power, portrait, icon;
  int assigned, left, player;
} EditorRow;
typedef struct {
  uint32_t page, focus, count, total, first, step, modal_focus, target;
  int active, picker, loading, setplay, centered, online;
  char title[64], subtitle[96], status[96], select_key[8], back_key[8];
  EditorRow rows[9];
} EditorPanel;

#ifndef PESNX_EDITOR_PREVIEW
static uint32_t editor_legacy_page(uint32_t side) {
  const uint32_t page=pes_controller_custom_prematch_gameplan_page(side);
  return page>=PES_PREMATCH_GAMEPLAN_PAGE_FORMATION ? UINT32_MAX : page;
}
static uint32_t editor_first(uint32_t total,uint32_t focus,uint32_t visible) {
  if(total<=visible)return 0;
  uint32_t first=focus>visible/2u ? focus-visible/2u : 0;
  return first+visible>total ? total-visible : first;
}
static void editor_snapshot(EditorPanel *v,uint32_t side,int setplay) {
  memset(v,0,sizeof(*v));v->setplay=setplay;
#ifdef PESNX_MANAGER_RENDER_ADAPTER
  if(!setplay&&manager_render_plan_active&&manager_render_plan.page==MD_PLAN_SETTINGS){
    const MdView *m=&manager_render_plan;v->active=v->online=1;v->centered=1;v->picker=m->plan_picker;
    v->page=m->plan_menu==3?PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS:PES_PREMATCH_GAMEPLAN_PAGE_FORMATION;
    v->focus=m->focus;v->first=m->first;v->count=m->count;v->total=m->total;
    fd_copy(v->title,sizeof(v->title),m->plan_menu==1?(m->plan_picker?"CHOOSE SHAPE":"FORMATION"):m->plan_menu==2?"TACTIC":m->plan_picker?"ASSIGN PLAYER":"PLAYER ROLES");
    for(unsigned i=0;i<v->count&&i<9;i++){const MdRow *r=&m->plan_rows[i];EditorRow *out=&v->rows[i];
      fd_copy(out->label,sizeof(out->label),r->label);fd_copy(out->value,sizeof(out->value),r->value);
      fd_copy(out->role,sizeof(out->role),manager_render_plan_role(r->role));out->portrait=r->portrait;out->player=r->identity!=0;
      out->power=r->rating;out->assigned=r->selected;
      out->icon=m->plan_menu==1?(m->plan_picker?11u:(uint32_t[]){5,11,7,8}[i]):m->plan_menu==3&&!m->plan_picker?(uint32_t[]){0,1,2,3,3,4,5,5,5}[i]:0;
    }return;
  }
#endif
  if(setplay) {
    v->active=v->picker=1;
    const uint32_t profile=android_controller_profile(pes_controller_set_piece_selector_owner_pad());
    fd_copy(v->select_key,sizeof(v->select_key),profile==PES_CONTROLLER_PROFILE_SINGLE_LEFT ? "DOWN" : profile==PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "X" : "A");
    fd_copy(v->back_key,sizeof(v->back_key),profile==PES_CONTROLLER_PROFILE_SINGLE_LEFT ? "LEFT" : profile==PES_CONTROLLER_PROFILE_SINGLE_RIGHT ? "A" : "B");
    v->total=pes_controller_set_piece_selector_count();
    v->focus=pes_controller_set_piece_selector_focus();
    fd_copy(v->title,sizeof(v->title),pes_controller_set_piece_selector_title());
    fd_copy(v->subtitle,sizeof(v->subtitle),"CHOOSE A TAKER");
  }else {
    v->page=pes_controller_custom_prematch_gameplan_page(side);
    if(v->page<PES_PREMATCH_GAMEPLAN_PAGE_FORMATION ||
        pes_controller_custom_prematch_gameplan_waiting(side))return;
    v->active=1;
    if(v->page==PES_PREMATCH_GAMEPLAN_PAGE_FORMATION) {
      v->picker=pes_controller_custom_prematch_gameplan_formation_picker_active(side);
      v->focus=pes_controller_custom_prematch_gameplan_formation_focus(side);
      v->first=pes_controller_custom_prematch_gameplan_formation_scroll(side);
      v->count=pes_controller_custom_prematch_gameplan_formation_row_count(side);
      if(v->count>9u)v->count=9u;
      fd_copy(v->title,sizeof(v->title),v->picker ? "CHOOSE SHAPE" : "FORMATION");
      snprintf(v->subtitle,sizeof(v->subtitle),"CURRENT SHAPE  -  %s",
          pes_controller_custom_prematch_gameplan_formation_label(side));
      static const char *const labels[]={"PLAYING STYLE","TEAM SHAPE","OFFSIDE TRAP","SUBSTITUTIONS"};
      for(uint32_t i=0;i<v->count;i++) {
        const uint32_t option=i+v->first;
        fd_copy(v->rows[i].label,sizeof(v->rows[i].label),v->picker
            ? pes_controller_custom_prematch_gameplan_formation_value(side,option) : labels[i%4u]);
        fd_copy(v->rows[i].value,sizeof(v->rows[i].value),v->picker ? ""
            : pes_controller_custom_prematch_gameplan_formation_value(side,i));
        v->rows[i].icon=v->picker ? 11u : (uint32_t[]){5,11,7,8}[i%4u];
        v->rows[i].assigned=v->picker && pes_controller_custom_prematch_gameplan_formation_option_active(side,option);
      }
      return;
    }
    if(v->page==PES_PREMATCH_GAMEPLAN_PAGE_PRESET) {
      v->step=pes_controller_custom_prematch_gameplan_preset_step(side);
      v->loading=pes_controller_custom_prematch_gameplan_preset_action(side)!=0;
      v->focus=pes_controller_custom_prematch_gameplan_preset_focus(side);
      v->modal_focus=v->focus;
      v->target=pes_controller_custom_prematch_gameplan_preset_target_slot(side);
      if(v->step>=2)v->focus=v->target;
      fd_copy(v->title,sizeof(v->title),v->step ? (v->loading ? "LOAD PRESET" : "SAVE PRESET") : "TEAM PRESETS");
      fd_copy(v->subtitle,sizeof(v->subtitle),"SQUAD TACTICS AND ROLES");
      fd_copy(v->status,sizeof(v->status),pes_controller_custom_prematch_gameplan_preset_status(side));
      v->count=v->step ? 3u : 2u;
      for(uint32_t i=0;i<v->count;i++) {
        v->rows[i].icon=v->step ? (v->loading ? 10u : 9u) : (i ? 10u : 9u);
        if(v->step) {
          snprintf(v->rows[i].label,sizeof(v->rows[i].label),"PRESET %02u",i+1u);
          fd_copy(v->rows[i].value,sizeof(v->rows[i].value),pes_controller_custom_prematch_gameplan_preset_exists(side,i) ? "SAVED" : "EMPTY");
        }else {
          fd_copy(v->rows[i].label,sizeof(v->rows[i].label),i ? "LOAD FORMATION" : "SAVE FORMATION");
          fd_copy(v->rows[i].value,sizeof(v->rows[i].value),i ? "Restore a saved setup" : "Store this team's setup");
        }
      }
      return;
    }
    v->picker=pes_controller_custom_prematch_gameplan_position_picker_active(side);
    const uint32_t role=pes_controller_custom_prematch_gameplan_position_focus(side);
    fd_copy(v->title,sizeof(v->title),v->picker ? "ASSIGN PLAYER" : "PLAYER ROLES");
    fd_copy(v->subtitle,sizeof(v->subtitle),v->picker
        ? pes_controller_custom_prematch_gameplan_position_label(role) : "SET-PIECE ROLES");
    if(!v->picker) {
      v->focus=role;v->count=PES_PREMATCH_GAMEPLAN_POSITION_COUNT;
      for(uint32_t i=0;i<v->count;i++) {
        fd_copy(v->rows[i].label,sizeof(v->rows[i].label),pes_controller_custom_prematch_gameplan_position_label(i));
        fd_copy(v->rows[i].value,sizeof(v->rows[i].value),pes_controller_custom_prematch_gameplan_position_value(side,i));
        v->rows[i].portrait=pes_controller_custom_prematch_gameplan_position_portrait_id(side,i);
        fd_copy(v->rows[i].role,sizeof(v->rows[i].role),pes_controller_custom_prematch_gameplan_position_role(side,i));
        v->rows[i].player=strcmp(v->rows[i].value,"NONE")!=0;
        v->rows[i].icon=(uint32_t[]){0,1,2,3,3,4,5,5,5}[i];
      }
      return;
    }
    v->focus=pes_controller_custom_prematch_gameplan_position_picker_focus(side);
    v->total=pes_controller_custom_prematch_gameplan_position_picker_count(side);
  }
  if(v->total && v->focus>=v->total)v->focus=v->total-1u;
  v->first=editor_first(v->total,v->focus,7);
  v->count=v->total-v->first;if(v->count>7u)v->count=7u;
  for(uint32_t i=0;i<v->count;i++) {
    const uint32_t index=v->first+i;EditorRow *r=&v->rows[i];
    fd_copy(r->label,sizeof(r->label),setplay ? pes_controller_set_piece_selector_name_at(index)
        : pes_controller_custom_prematch_gameplan_position_picker_name(side,index));
    fd_copy(r->role,sizeof(r->role),setplay ? pes_controller_set_piece_selector_position_at(index)
        : pes_controller_custom_prematch_gameplan_position_picker_role(side,index));
    r->player=strcmp(r->label,"NONE")!=0;
    r->assigned=setplay ? pes_controller_set_piece_selector_current_at(index)
        : pes_controller_custom_prematch_gameplan_position_picker_assigned(side,index);
    r->portrait=setplay ? pes_controller_set_piece_selector_portrait_at(index)
        : pes_controller_custom_prematch_gameplan_position_picker_portrait_id(side,index);
    r->left=setplay ? !strncmp(pes_controller_set_piece_selector_foot_at(index),"LEFT",4)
        : pes_controller_custom_prematch_gameplan_position_picker_preferred_foot(side,index)!=0;
    r->power=setplay ? pes_controller_set_piece_selector_ability_at(index)
        : pes_controller_custom_prematch_gameplan_position_picker_shot_power(side,index);
  }
}

/* Rendering only touches the GPU cache; missing IDs cross to the game thread. */
static void editor_request_portraits(const EditorPanel *v,uint32_t side) {
  for(uint32_t i=0;i<v->count && i<9;i++) {
    const uint32_t id=v->rows[i].portrait;
    if(id && !gameplan_portrait_texture(id))
      pes_controller_editor_request_portrait(side,i,id);
  }
}
#endif

/* Sprite IDs follow art/gameplan/icons-v1.json; one atlas upload per context. */
static void editor_icon(MasterLeagueRender *ui,uint32_t id,float x,float y,float h,GLfloat *verts,int *quads) {
  if(id>=16u)return;
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=gl.gameplan_icons_tex;
  static const uint16_t bounds[16][4]={
    {39,105,305,303},
    {410,67,604,310},
    {663,67,858,310},
    {947,76,1237,332},
    {32,388,310,620},
    {348,399,623,610},
    {660,361,893,620},
    {970,350,1193,624},
    {41,661,287,885},
    {354,633,612,900},
    {653,673,918,903},
    {954,666,1225,875},
    {68,917,219,1205},
    {406,917,557,1205},
    {658,945,896,1183},
    {969,938,1225,1192}};
  const float sw=bounds[id][2]-bounds[id][0],sh=bounds[id][3]-bounds[id][1];
  const float box=h*screen_height,iw=box*sw/fmaxf(sw,sh),ih=box*sh/fmaxf(sw,sh);
  *quads+=emit_image_rect_uv(x*screen_width+(box-iw)*.5f,y*screen_height+(box-ih)*.5f,iw,ih,
      bounds[id][0]/1254.f,bounds[id][1]/1254.f,bounds[id][2]/1254.f,bounds[id][3]/1254.f,verts+*quads*24);
}
static void editor_portrait(MasterLeagueRender *ui,const EditorRow *r,float x,float y,float h,GLfloat *verts,int *quads) {
  const GLuint tex=r->portrait ? gameplan_portrait_texture(r->portrait) : 0;
  if(tex)ml_ui_image(ui,tex,0,x,y,h*screen_height/screen_width,h,verts,quads);
  else if(r->player)editor_icon(ui,15,x,y,h,verts,quads);
}
static void editor_foot_pair(MasterLeagueRender *ui,int left,float x,float cy,GLfloat *verts,int *quads) {
  const float h=.046f,span=.029f;
  for(uint32_t foot=0;foot<2u;foot++) {
    const uint32_t before=ui->draw_count;
    editor_icon(ui,12u+foot,x+foot*span,cy-h*.5f,h,verts,quads);
    if(ui->draw_count>before)
      ui->draws[before].color[3]=(foot==0u)==(left!=0) ? 1.f : .20f;
  }
}
static void editor_role_plate(MasterLeagueRender *ui,const char *role,float x,float cy,float w,GLfloat *verts,int *quads) {
  if(!role[0])return;
  const uint32_t band=!strcmp(role,"GK") ? 0u : (!strcmp(role,"CB") || !strcmp(role,"LB") || !strcmp(role,"RB")) ? 1u
      : (strchr(role,'M') ? 2u : 3u);
  static const float colors[4][3]={{.96f,.55f,.10f},{.08f,.45f,.88f},{.05f,.65f,.35f},{.88f,.18f,.20f}};
  fd_rect(ui,x,cy-.014f,w,.028f,colors[band][0],colors[band][1],colors[band][2],verts,quads);
  fd_center_text(ui,role,x,cy,w,.0185f,-1,verts,quads);
}

static void editor_preset_modal(MasterLeagueRender *ui,const EditorPanel *v,float x,float y,float w,float h,
    GLfloat *verts,int *quads) {
  if(v->page!=PES_PREMATCH_GAMEPLAN_PAGE_PRESET || v->step<2u)return;
  const uint32_t shade=ui->draw_count;
  fd_rect(ui,x,y,w,h,.02f,.045f,.12f,verts,quads);
  for(uint32_t i=shade;i<ui->draw_count;i++)ui->draws[i].color[3]=.72f;
  const float mh=v->step==4u ? .272f : .242f;
  const float mx=x+.025f,my=y+(h-mh)*.5f,mw=w-.050f;
  fd_rect(ui,mx,my,mw,mh,1,1,1,verts,quads);
  editor_icon(ui,v->step==3u ? 14u : v->loading ? 10u : 9u,mx+.017f,my+.020f,.064f,verts,quads);
  const char *title=v->step==2u ? (v->loading ? "LOAD THIS PRESET?" : "OVERWRITE PRESET?")
      : v->step==3u ? (v->loading ? "PRESET LOADED" : "PRESET SAVED") : "PRESET UNAVAILABLE";
  fd_text(ui,title,mx+.065f,my+.031f,mw-.081f,.029f,-2,verts,quads);
  char slot[40];snprintf(slot,sizeof(slot),"PRESET %02u",v->target+1u);
  fd_text(ui,slot,mx+.021f,my+.092f,mw-.042f,.023f,-2,verts,quads);
  const char *message=v->step==2u ? (v->loading ? "Replace your current setup?" : "Replace the setup saved in this slot?")
      : v->step==3u ? "Your lineup, tactics and roles are ready." : v->status;
  fd_text(ui,message,mx+.021f,my+.128f,mw-.042f,.022f,-3,verts,quads);
  if(v->step==4u && v->loading)
    fd_text(ui,"Older presets may need saving again.",mx+.021f,my+.160f,mw-.042f,.020f,-3,verts,quads);
  const uint32_t count=v->step==2u ? 2u : 1u;
  const float bw=(mw-.052f)/2.f,by=my+mh-.072f;
  for(uint32_t i=0;i<count;i++) {
    const float bx=mx+.021f+(count==1u ? (mw-.042f-bw)*.5f : i*(bw+.010f));
    const int active=count==1u || v->modal_focus==i;
    fd_rect(ui,bx,by,bw,.051f,active?.025f:.937f,active?.30f:.965f,active?.86f:.988f,verts,quads);
    fd_center_text(ui,count==1u ? "OK" : i ? "CANCEL" : v->loading ? "LOAD" : "OVERWRITE",
        bx,by+.0255f,bw,.023f,active?-1:-2,verts,quads);
  }
}

static void editor_panel_emit(MasterLeagueRender *ui,const EditorPanel *v,
    uint32_t side,GLfloat *verts,int *quads) {
  if(!v->active)return;
  const float x=v->setplay ? .20f : v->centered ? .2625f : .018f+side*.489f;
  const float w=v->setplay ? .60f : .475f;
  const float h=v->setplay ? .168f+fmaxf(1.f,fminf(v->count,7.f))*.062f+.070f : .651f;
  const float y=v->setplay ? (.98f-h)*.5f : .153f;
  const float left=x+.020f,right=x+w-.020f;
  fd_rect(ui,x,y,w,h,1,1,1,verts,quads);
  fd_art(ui,2,left,y+.012f,w-.040f,.106f,verts,quads);
  editor_icon(ui,v->setplay ? 3u : v->page==PES_PREMATCH_GAMEPLAN_PAGE_PRESET ? 9u : v->page==PES_PREMATCH_GAMEPLAN_PAGE_FORMATION ? 11u : 0u,
      left+.010f,y+.024f,.080f,verts,quads);
  ml_ui_text(ui,v->title,left+.064f,y+.026f,w-.122f,.031f,1,-1,0,1,verts,quads);
  fd_text(ui,v->subtitle,left+.064f,y+.077f,w-.122f,.0195f,-1,verts,quads);
  const int players=v->picker && v->page!=PES_PREMATCH_GAMEPLAN_PAGE_FORMATION;
  const int presets=v->page==PES_PREMATCH_GAMEPLAN_PAGE_PRESET;
  const int roles=v->page==PES_PREMATCH_GAMEPLAN_PAGE_POSITIONS && !players;
  float row_y=y+.168f;
  const float step=players ? .062f : roles ? .051f : presets ? .117f : v->picker ? .077f : .105f;
  const float row_h=step-.007f;
  if(players) {
    fd_text(ui,"PLAYER",left+.096f,y+.139f,.25f,.019f,-3,verts,quads);
    if(!v->online)fd_text(ui,"FOOT",right-.099f,y+.139f,.046f,.018f,-3,verts,quads);
    fd_text(ui,v->online?"OVR":"PWR",right-.033f,y+.139f,.033f,.018f,-3,verts,quads);
  }else if(roles) {
    fd_text(ui,"ASSIGNMENT",left+.012f,y+.139f,.18f,.019f,-3,verts,quads);
    fd_text(ui,"PLAYER",left+.233f,y+.139f,.18f,.019f,-3,verts,quads);
  }else if(presets) {
    fd_text(ui,"THREE SAVED SETUPS PER TEAM",left+.012f,y+.139f,w-.064f,.019f,-3,verts,quads);
  }
  for(uint32_t i=0;i<v->count && i<9u;i++) {
    const EditorRow *r=&v->rows[i];const float ry=row_y+i*step;
    const int selected=v->first+i==v->focus,ink=selected ? -1 : -2;
    fd_rect(ui,left,ry,right-left,row_h,selected ? .025f : .937f,
        selected ? .30f : .965f,selected ? .86f : .988f,verts,quads);
    if(selected)fd_rect(ui,left,ry+.009f,.003f,row_h-.018f,.0f,.83f,.95f,verts,quads);
    const float cy=ry+row_h*.5f;
    if(players) {
      editor_portrait(ui,r,left+.006f,cy-.026f,.052f,verts,quads);
      if(r->player)editor_role_plate(ui,r->role,left+.039f,cy,.042f,verts,quads);
      fd_text(ui,r->label,left+.091f,fd_cap_top(cy,.023f),right-left-.217f,.023f,ink,verts,quads);
      if(r->player) {
        if(!v->online)editor_foot_pair(ui,r->left,right-.112f,cy,verts,quads);
        char value[8];snprintf(value,sizeof(value),"%u",r->power);
        fd_center_text(ui,value,right-.036f,cy,.031f,.024f,ink,verts,quads);
      }
      if(r->assigned)editor_icon(ui,14,left+.028f,ry+.031f,.022f,verts,quads);
    }else if(roles) {
      editor_icon(ui,r->icon,left+.005f,cy-.020f,.040f,verts,quads);
      fd_text(ui,r->label,left+.033f,fd_cap_top(cy,.0188f),.163f,.0188f,ink,verts,quads);
      editor_portrait(ui,r,left+.200f,cy-.022f,.044f,verts,quads);
      fd_text(ui,r->value,left+.233f,fd_cap_top(cy,.021f),right-left-.288f,.021f,ink,verts,quads);
      if(r->player)editor_role_plate(ui,r->role,right-.043f,cy,.038f,verts,quads);
    }else {
      const float ih=v->picker ? .051f : .072f;
      editor_icon(ui,r->icon,left+.012f,cy-ih*.5f,ih,verts,quads);
      fd_text(ui,r->label,left+.065f,ry+.015f,w-.139f,.025f,ink,verts,quads);
      if(r->value[0])fd_text(ui,r->value,left+.065f,ry+.060f,w-.139f,.022f,ink,verts,quads);
      if(r->assigned)editor_icon(ui,14,right-.035f,cy-.020f,.040f,verts,quads);
    }
  }
  if(v->total>v->count && v->total) {
    const float rail=v->count*step-.007f;
    const float thumb=rail*v->count/v->total;
    fd_rect(ui,right+.008f,row_y,.002f,rail,.85f,.9f,.94f,verts,quads);
    fd_rect(ui,right+.008f,row_y+(rail-thumb)*v->first/(v->total-v->count),.002f,thumb,.02f,.40f,.80f,verts,quads);
  }
  if(v->status[0] && v->step<2u)fd_text(ui,v->status,left+.012f,y+h-.054f,w-.064f,.022f,-3,verts,quads);
  if(players && !v->count)fd_text(ui,"LOADING PLAYERS",left+.012f,row_y+.012f,w-.064f,.023f,-3,verts,quads);
  if(v->setplay) {
    fd_rect(ui,left,y+h-.064f,w-.040f,.050f,.963f,.977f,.99f,verts,quads);
    float hx=left+.009f;
    const char *keys[]={v->select_key,v->back_key};const char *labels[]={"SELECT","BACK"};
    for(uint32_t i=0;i<2;i++) {
      const float ih=.037f,iw=ih*screen_height/screen_width;
      ml_ui_image(ui,switch_button_texture(keys[i]),0,hx,y+h-.063f,iw,ih,verts,quads);
      fd_text(ui,labels[i],hx+iw+.008f,fd_cap_top(y+h-.0445f,.023f),.095f,.023f,-2,verts,quads);
      hx+=.16f;
    }
  }
  editor_preset_modal(ui,v,x,y,w,h,verts,quads);
}
