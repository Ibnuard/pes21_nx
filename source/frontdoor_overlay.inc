/* Flat Matchday: presentation only. The native controller still owns every
 * route, focus, team ID, ready flag, kit, lineup and kickoff transaction.
 * A bounded value snapshot also lets the host preview exercise this exact
 * renderer without booting the game or touching a save. */
typedef enum {
  FD_NONE, FD_TITLE, FD_MENU, FD_MATCH, FD_MODES, FD_SELECTOR,
  FD_HUB, FD_KITS, FD_STADIUM, FD_SETTINGS,
  FD_VIDEO, FD_INFO, FD_LOADING, FD_VS, FD_PAUSE, FD_PAUSE_SETTINGS, FD_RESULT
} FrontdoorPage;
typedef struct {
  char label[96], value[96];
  uint32_t badge;
  int relative;
} FrontdoorRow;
typedef struct {
  char owner[24], title[96], name[96], lineup[11][64];
  FrontdoorRow neighbours[4];
  uint32_t phase, badge, ratings[3], grade, neighbour_count, lineup_count;
  uint32_t kit_count, kit_index, kit_number;
  int active, ready, stats_valid;
  float ready_mix;
} FrontdoorSide;
typedef struct {
  FrontdoorPage page;
  uint32_t focus, side_count, row_count, total_rows, first_row, action_count;
  uint32_t portrait_previous, portrait_current;
  float portrait_mix;
  float menu_weights[4];
  float menu_pattern_phase;
  int exhibition, kit_editing, confirm;
  uint32_t confirm_focus;
  float motion_phase;
  char title[112], subtitle[112], status[112], score[2][16], stats[2][8][24];
  FrontdoorSide sides[2];
  FrontdoorRow rows[6];
} FrontdoorView;

typedef struct {
  float from[4], weights[4];
  uint64_t started_ns, loop_started_ns;
  float pattern_phase;
  uint32_t target;
  int initialized;
} FrontdoorMenuMotion;

/* Fixed-duration, frame-rate-independent accordion. Retarget from the current
 * pose, not the previous selected row, so quick taps/reversals never snap.
 * Weights always sum to one: expanding one row cannot grow the whole rail. */
static void fd_menu_motion_step(FrontdoorMenuMotion *motion,int active,
    uint32_t focus,uint64_t now_ns) {
  focus%=4u;
  if(!active) {
    memset(motion,0,sizeof(*motion));
    return;
  }
  if(!motion->initialized) {
    motion->initialized=1;motion->target=focus;motion->started_ns=now_ns;
    motion->loop_started_ns=now_ns;
    motion->from[focus]=motion->weights[focus]=1.f;
    return;
  }
  const uint64_t loop_elapsed=now_ns>=motion->loop_started_ns ? now_ns-motion->loop_started_ns : 0;
  motion->pattern_phase=(float)(loop_elapsed%6000000000ULL)/6000000000.f;
  float t=now_ns>=motion->started_ns ? (float)(now_ns-motion->started_ns)/260000000.f : 0.f;
  t=fminf(1.f,t);
  const float ease=1.f-(1.f-t)*(1.f-t)*(1.f-t);
  for(uint32_t i=0;i<4u;i++)
    motion->weights[i]=motion->from[i]+((i==motion->target ? 1.f : 0.f)-motion->from[i])*ease;
  if(focus!=motion->target) {
    memcpy(motion->from,motion->weights,sizeof(motion->from));
    motion->target=focus;motion->started_ns=now_ns;
  }
}

static void fd_copy(char *to,size_t size,const char *from) {
  snprintf(to,size,"%s",from ? from : "");
}
static void frontdoor_snapshot(FrontdoorView *v,FrontdoorPage page,
    uint32_t menu_focus,uint32_t previous,uint32_t current,float mix,
    const float ready_mix[2]) {
  memset(v,0,sizeof(*v));v->page=page;v->focus=menu_focus;
  v->menu_weights[menu_focus%4u]=1.f;
  v->portrait_previous=previous%4u;v->portrait_current=current%4u;v->portrait_mix=mix;
  v->exhibition=pes_controller_exhibition_single_controller_mode();
  v->side_count=2;
  if(page==FD_MATCH || page==FD_MODES) {
    v->focus=competition_frontend_focus();
    v->row_count=page==FD_MATCH ? 2u : 3u;
    for(uint32_t i=0;i<v->row_count;i++) {
      fd_copy(v->rows[i].label,sizeof(v->rows[i].label),competition_frontend_item_label(i));
      if(!v->rows[i].label[0]) {
        static const char *const matches[]={"EXHIBITION","2 PLAYER"};
        static const char *const modes[]={"CUP","LEAGUE","MASTER LEAGUE"};
        fd_copy(v->rows[i].label,sizeof(v->rows[i].label),page==FD_MATCH ? matches[i] : modes[i]);
      }
    }
    fd_copy(v->status,sizeof(v->status),competition_frontend_status());
  }
  if(page==FD_SELECTOR) {
    const int picker=competition_frontend_cup_team_picker_active();
    v->side_count=picker ? 1u : 2u;
    v->exhibition=!picker && pes_controller_2p_team_selector_exhibition_mode();
    const uint32_t active=pes_controller_2p_team_selector_active_side();
    for(uint32_t side=0;side<v->side_count;side++) {
      FrontdoorSide *s=&v->sides[side];
      s->phase=pes_controller_2p_team_selector_phase(side);
      s->active=!v->exhibition || side==active;
      s->ready=pes_controller_2p_team_selector_confirmed(side);
      s->ready_mix=ready_mix ? ready_mix[side] : 1.f;
      fd_copy(s->owner,sizeof(s->owner),side ? (v->exhibition ? "COM / AWAY" : "P2 / AWAY") : "P1 / HOME");
      if(picker) {
        const CompetitionEntryDraft *draft=competition_frontend_cup_draft();
        const uint32_t slot=competition_frontend_cup_bracket_slot_focus();
        const uint32_t owner=draft && slot<draft->team_count ? draft->owners[slot] : 0u;
        if(owner)snprintf(s->owner,sizeof(s->owner),"PLAYER %u",owner);
        else fd_copy(s->owner,sizeof(s->owner),"COM");
      }
      fd_copy(s->title,sizeof(s->title),pes_controller_2p_team_selector_title(side));
      const uint32_t focus=pes_controller_2p_team_selector_focus(side);
      fd_copy(s->name,sizeof(s->name),pes_controller_2p_team_selector_label(side,focus));
      s->badge=pes_controller_2p_team_selector_badge(side,focus);
      s->stats_valid=pes_controller_2p_team_selector_team_stats(side,
          &s->ratings[0],&s->ratings[1],&s->ratings[2],&s->grade);
      const uint32_t start=pes_controller_2p_team_selector_scroll(side);
      const uint32_t count=pes_controller_2p_team_selector_visible_count(side);
      for(uint32_t i=0;i<count && i<32u && s->neighbour_count<4u;i++) {
        const int relative=(int)(start+i)-(int)focus;
        if(!relative || relative < -2 || relative > 2)continue;
        FrontdoorRow *row=&s->neighbours[s->neighbour_count++];row->relative=relative;
        fd_copy(row->label,sizeof(row->label),pes_controller_2p_team_selector_label(side,start+i));
        row->badge=pes_controller_2p_team_selector_badge(side,start+i);
      }
    }
  }
  if((page>=FD_HUB && page<=FD_SETTINGS) || page==FD_VS || page==FD_PAUSE || page==FD_RESULT) {
    v->focus=page==FD_HUB ? pes_controller_2p_prematch_hub_focus() : pes_controller_2p_prematch_hub_page_focus();
    v->action_count=pes_controller_2p_prematch_hub_button_count();
    if(v->action_count>5u)v->action_count=5u;
    for(uint32_t side=0;side<2u;side++) {
      FrontdoorSide *s=&v->sides[side];
      /* HOME/AWAY remains correct for Cup/League owners, spectators and ML. */
      fd_copy(s->owner,sizeof(s->owner),side ? "AWAY" : "HOME");
      fd_copy(s->name,sizeof(s->name),pes_controller_2p_prematch_hub_team_name(side));
      s->badge=pes_controller_2p_prematch_hub_badge(side);
      if(page==FD_RESULT)continue;
      s->lineup_count=pes_controller_2p_prematch_hub_lineup_count(side);
      if(s->lineup_count>11u)s->lineup_count=11u;
      for(uint32_t i=0;i<s->lineup_count;i++)
        fd_copy(s->lineup[i],sizeof(s->lineup[i]),pes_controller_2p_prematch_hub_lineup_name(side,i));
      s->kit_count=pes_controller_2p_prematch_hub_kit_count(side);
      s->kit_index=pes_controller_2p_prematch_hub_kit_index(side);
      s->kit_number=pes_controller_2p_prematch_hub_kit_number(side);
    }
    static const char *const stadium[]={"AUTO STADIUM","HOME STADIUM","AWAY STADIUM"};
    snprintf(v->subtitle,sizeof(v->subtitle),"%s / %s / %s",
        stadium[pes_controller_2p_prematch_hub_stadium_index()%3u],
        pes_controller_stadium_is_day() ? "DAY" : "NIGHT",
        pes_controller_stadium_weather() ? "CLOUDY" : "FINE");
  }
  if(page==FD_KITS)v->kit_editing=pes_controller_2p_prematch_kit_editing();
  if(page==FD_STADIUM) {
    static const char *const labels[]={"STADIUM","MATCH TIME","WEATHER","SEASON","GRASS LENGTH","PITCH CONDITION"};
    static const char *const stadium[]={"AUTO","HOME","AWAY"};
    static const char *const grass[]={"SHORT","NORMAL","LONG"};
    static const char *const pitch[]={"DRY","NORMAL","WET"};
    const char *values[]={stadium[pes_controller_2p_prematch_hub_stadium_index()%3u],
      pes_controller_stadium_is_day() ? "DAY" : "NIGHT",
      pes_controller_stadium_weather() ? "CLOUDY" : "FINE",
      pes_controller_stadium_season() ? "WINTER" : "SUMMER",
      grass[pes_controller_stadium_turf_length()%3u],pitch[pes_controller_stadium_pitch_condition()%3u]};
    v->row_count=v->total_rows=6;
    for(uint32_t i=0;i<6u;i++) {
      fd_copy(v->rows[i].label,sizeof(v->rows[i].label),labels[i]);
      fd_copy(v->rows[i].value,sizeof(v->rows[i].value),values[i]);
    }
  }
  if(page==FD_SETTINGS || page==FD_PAUSE_SETTINGS || page==FD_VIDEO) {
    const int pause=page==FD_PAUSE_SETTINGS,video=page==FD_VIDEO;
    v->focus=pause ? pes_controller_pause_settings_focus() : video ? pes_controller_custom_video_settings_focus() : pes_controller_custom_match_settings_focus();
    v->total_rows=pause ? pes_controller_pause_settings_count() : video ? 2u : pes_controller_custom_match_settings_count();
    v->row_count=v->total_rows<6u ? v->total_rows : 6u;
    if(v->row_count && v->focus>=v->row_count)v->first_row=v->focus-v->row_count+1u;
    fd_copy(v->title,sizeof(v->title),pause ? pes_controller_pause_settings_title() : video ? "VIDEO SETTINGS" : "GENERAL SETTINGS");
    for(uint32_t i=0;i<v->row_count;i++) {
      const uint32_t row=v->first_row+i;
      fd_copy(v->rows[i].label,sizeof(v->rows[i].label),pause ? pes_controller_pause_settings_label(row) : video ? pes_controller_custom_video_settings_label(row) : pes_controller_custom_match_settings_label(row));
      fd_copy(v->rows[i].value,sizeof(v->rows[i].value),pause ? pes_controller_pause_settings_value(row) : video ? pes_controller_custom_video_settings_value(row) : pes_controller_custom_match_settings_value(row));
    }
  }
  if(page==FD_INFO) {
    fd_copy(v->title,sizeof(v->title),pes_controller_custom_info_popup_title());
    v->row_count=pes_controller_custom_info_popup_line_count();
    if(v->row_count>6u)v->row_count=6u;
    for(uint32_t i=0;i<v->row_count;i++)fd_copy(v->rows[i].label,sizeof(v->rows[i].label),pes_controller_custom_info_popup_line(i));
  }
  if(page==FD_PAUSE) {
    v->focus=pes_controller_pause_skin_focus();
    v->confirm=pes_controller_pause_top_menu_confirm_active();
    v->confirm_focus=pes_controller_pause_top_menu_confirm_focus();
  }
  if(page==FD_RESULT) {
    fd_copy(v->title,sizeof(v->title),pes_controller_match_result_heading());
    v->action_count=pes_controller_match_result_card_count();
    if(v->action_count>3u)v->action_count=3u;
    v->focus=pes_controller_match_result_focus();
    for(uint32_t i=0;i<v->action_count;i++) {
      const char *label=pes_controller_match_result_card_label(i);
      fd_copy(v->rows[i].label,sizeof(v->rows[i].label),label);
      if(!strncmp(label,"BACK TO ",8) || !strcmp(label,"TOP TO MENU"))
        fd_copy(v->status,sizeof(v->status),label);
    }
  }
  if(page==FD_PAUSE || page==FD_RESULT) {
    for(uint32_t side=0;side<2u;side++) {
      uint32_t value;
      if(pes_controller_pause_score(side,&value))snprintf(v->score[side],sizeof(v->score[side]),"%u",value);
      else fd_copy(v->score[side],sizeof(v->score[side]),"--");
      for(uint32_t row=0;row<8u;row++) {
        if(pes_controller_pause_stat(side,row,&value))snprintf(v->stats[side][row],sizeof(v->stats[side][row]),row ? "%u" : "%u%%",value);
        else fd_copy(v->stats[side][row],sizeof(v->stats[side][row]),"--");
      }
    }
  }
}

static void fd_rect(MasterLeagueRender *ui,float x,float y,float w,float h,
    float r,float g,float b,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x,y,w,h,r,g,b,1,-1,0,1,verts,quads);
}
static void fd_text(MasterLeagueRender *ui,const char *text,float x,float y,float w,float h,
    int ink,GLfloat *verts,int *quads) {
  ml_ui_text(ui,text,x,y,w,h,0,ink,0,1,verts,quads);
}
/* Align visible capitals, not the padded font cell. Cache once per atlas LOD;
 * the same formula centres both small hub buttons and large controller hints. */
static float fd_cap_top(float center,float height) {
  static float cap_center[4];
  const uint32_t level=efootball_raster_level(height*screen_height,0);
  if(cap_center[level]<=0.f) {
    const uint32_t h=(uint32_t)efootball_raster_height(level),w=(uint32_t)efootball_raster_width(level);
    const uint32_t gx=(uint32_t)efootball_font_glyph_index('H')*EFOOTBALL_FONT_CELL_W;
    const uint32_t gy=(EFOOTBALL_FONT_BOLD+level*EFOOTBALL_FONT_WEIGHTS)*EFOOTBALL_FONT_CELL_H;
    uint32_t first=h,last=0;
    for(uint32_t yy=0;yy<h;yy++)for(uint32_t xx=0;xx<w;xx++)
      if(efootball_font_atlas_alpha[(gy+yy)*EFOOTBALL_FONT_ATLAS_W+gx+xx]>64u) {
        if(yy<first)first=yy;
        if(yy>last)last=yy;
      }
    cap_center[level]=first<=last ? (first+last+1.f)/(2.f*h) : .5f;
  }
  return center-height*cap_center[level];
}
static void fd_center_text(MasterLeagueRender *ui,const char *text,float x,float cy,float w,
    float h,int ink,GLfloat *verts,int *quads) {
  const float tw=fminf(w,measure_efootball_line_mode(text,(int)strlen(text),h*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width);
  fd_text(ui,text,x+(w-tw)*.5f,fd_cap_top(cy,h),tw+.002f,h,ink,verts,quads);
}
static void fd_art(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float w,float h,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=gl.frontdoor_panels_tex;
  /* Four authored 1536x256 strips; crop to fill without stretching patterns.
   * A 2px gutter avoids neighbouring red/blue strips bleeding at minification. */
  const float aspect=w*screen_width/(h*screen_height),native=1532.f/252.f;
  const float uw=aspect<native ? (1532.f/1536.f)*aspect/native : 1532.f/1536.f;
  const float vh=aspect>native ? (252.f/1024.f)*native/aspect : 252.f/1024.f;
  const float u=(1.f-uw)*.5f,v=(sprite%4u)*.25f+(.25f-vh)*.5f;
  d->uv[0]=u;d->uv[1]=v;d->uv[2]=uw;d->uv[3]=vh;
  d->round=(RoundedRectStyle){w*screen_width,h*screen_height,.012f*screen_height};
  *quads+=emit_image_rect_uv(x*screen_width,y*screen_height,w*screen_width,h*screen_height,u,v,u+uw,v+vh,verts+*quads*24);
}
static void fd_brand(MasterLeagueRender *ui,float x,float y,float w,GLfloat *verts,int *quads) {
  ml_ui_image(ui,gl.main_menu_brand_tex,0,x,y,w,w*screen_width/screen_height*(496.f/1310.f),verts,quads);
  /* Keep the existing logo silhouette, using alpha-only navy ink on white. */
  MlDraw *d=&ui->draws[ui->draw_count-1u];d->kind=4;
  d->color[0]=.025f;d->color[1]=.09f;d->color[2]=.27f;
}
/* Animate the selected card's sample window, not its geometry. A modest zoom
 * leaves room for a seamless six-second elliptical drift inside this strip.
 * Both vertex UVs and rounded-mask UVs follow the crop; no wrapping into the
 * adjacent red/navy strips and no movement of the border, icon or title. */
static void fd_menu_pattern_loop(MasterLeagueRender *ui,float phase,GLfloat *verts) {
  if(!ui->draw_count)return;
  MlDraw *d=&ui->draws[ui->draw_count-1u];
  if(d->kind!=2 || d->texture!=gl.frontdoor_panels_tex)return;
  const float old_u=d->uv[0],old_v=d->uv[1],old_w=d->uv[2],old_h=d->uv[3];
  const float w=old_w*.88f,h=old_h*.88f,angle=phase*6.28318530718f;
  const float u=.5f-w*.5f+sinf(angle)*fminf((1532.f/1536.f-w)*.5f,old_w*.055f);
  const float v=.875f-h*.5f+cosf(angle)*(252.f/1024.f-h)*.41f;
  for(uint32_t i=0;i<6u;i++) {
    GLfloat *vertex=verts+d->first*24+i*4;
    vertex[2]=u+(vertex[2]-old_u)*w/old_w;
    vertex[3]=v+(vertex[3]-old_v)*h/old_h;
  }
  d->uv[0]=u;d->uv[1]=v;d->uv[2]=w;d->uv[3]=h;
}
static void fd_action_content(MasterLeagueRender *ui,const char *label,uint32_t icon,
    float x,float y,float w,float h,float text_h,int ink,GLfloat *verts,int *quads) {
  const float ih=.046f,iw=ih*screen_height/screen_width,gap=.010f;
  const float tw=fminf(w-iw-gap-.020f,measure_efootball_line_mode(label,(int)strlen(label),text_h*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width);
  const float gx=x+(w-(iw+gap+tw))*.5f,cy=y+h*.5f;
  ml_ui_header_icon(ui,icon,gx,cy-ih*.5f,ih,verts,quads);
  fd_text(ui,label,gx+iw+gap,fd_cap_top(cy,text_h),tw+.002f,text_h,ink,verts,quads);
}
static void fd_card(MasterLeagueRender *ui,float x,float y,float w,float h,
    int selected,int red,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x,y+.006f,w,h,.08f,.15f,.26f,.13f,-1,0,1,verts,quads);
  if(selected) {
    fd_rect(ui,x-.003f,y-.005f,w+.006f,h+.010f,red ? .89f : .02f,red ? .12f : .43f,red ? .20f : .86f,verts,quads);
    fd_rect(ui,x,y,w,h,1,1,1,verts,quads);
    fd_art(ui,red ? 1u : 3u,x+.002f,y+.0035f,w-.004f,h-.007f,verts,quads);
  }else fd_rect(ui,x,y,w,h,1,1,1,verts,quads);
}
static void fd_header(MasterLeagueRender *ui,const char *title,const char *subtitle,
    uint32_t icon,GLfloat *verts,int *quads) {
  fd_art(ui,2,.03f,.028f,.94f,.128f,verts,quads);
  ml_ui_text(ui,title,.055f,.048f,.68f,.0444f,1,-1,0,1,verts,quads);
  fd_text(ui,subtitle,.055f,.107f,.80f,.025f,-1,verts,quads);
  ml_ui_header_icon(ui,icon,.91f,.056f,.072f,verts,quads);
}
static void fd_helper(MasterLeagueRender *ui,const char *key,const char *label,
    float *x,GLfloat *verts,int *quads) {
  const float h=.0528f,w=h*screen_height/screen_width;
  ml_ui_image(ui,switch_button_texture(key),0,*x,.928f,w,h,verts,quads);
  const float textw=measure_efootball_line_mode(label,(int)strlen(label),.0333f*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width;
  fd_text(ui,label,*x+w+.010f,fd_cap_top(.9544f,.0333f),textw+.004f,.0333f,-1,verts,quads);
  *x+=w+.010f+textw+.033f;
}
static void fd_footer(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  const FrontdoorPage page=v->page;
  if(page==FD_TITLE || page==FD_LOADING || page==FD_VS)return;
  fd_rect(ui,0,.912f,1,.088f,.025f,.09f,.24f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0;
  float x=.035f;
  if(page==FD_INFO)fd_helper(ui,"B","BACK",&x,verts,quads);
  else if(page==FD_KITS) {
    if(!v->kit_editing)fd_helper(ui,"A","SELECT KIT",&x,verts,quads);
    fd_helper(ui,"B",v->kit_editing ? "DONE" : "BACK",&x,verts,quads);
    fd_helper(ui,"LEFT",v->kit_editing ? "PREV KIT" : "LEFT",&x,verts,quads);
    fd_helper(ui,">",v->kit_editing ? "NEXT KIT" : "RIGHT",&x,verts,quads);
  }else if(page==FD_PAUSE) {
    fd_helper(ui,"A","SELECT",&x,verts,quads);
    fd_helper(ui,"B",v->confirm ? "CANCEL" : "RESUME MATCH",&x,verts,quads);
    fd_helper(ui,"LEFT","PREVIOUS",&x,verts,quads);
    fd_helper(ui,">","NEXT",&x,verts,quads);
  }else if(page==FD_RESULT) {
    fd_helper(ui,"A","CONFIRM",&x,verts,quads);
    if(v->status[0])fd_helper(ui,"B",v->status,&x,verts,quads);
    if(v->action_count>1u) {
      fd_helper(ui,"LEFT","PREVIOUS",&x,verts,quads);
      fd_helper(ui,">","NEXT",&x,verts,quads);
    }
  }else {
    fd_helper(ui,"A",page==FD_SELECTOR ? "CONFIRM" : page>=FD_KITS ? "CHANGE" : "SELECT",&x,verts,quads);
    if(page!=FD_MENU)fd_helper(ui,"B","BACK",&x,verts,quads);
    if(page==FD_VIDEO)fd_helper(ui,"X","APPLY",&x,verts,quads);
    if(page==FD_SELECTOR) {
      fd_helper(ui,"UP","PREVIOUS",&x,verts,quads);
      fd_helper(ui,"DOWN","NEXT",&x,verts,quads);
    }else if(page==FD_MENU) {
      fd_helper(ui,"UP","PREVIOUS",&x,verts,quads);
      fd_helper(ui,"DOWN","NEXT",&x,verts,quads);
    }else if(page>=FD_KITS) {
      fd_helper(ui,"LEFT","PREV VALUE",&x,verts,quads);
      fd_helper(ui,">","NEXT VALUE",&x,verts,quads);
    }
  }
}
/* Clipped image UVs keep slide-in/out poses inside the fixed overlay VBO. */
static void fd_sliding_image(MasterLeagueRender *ui,GLuint texture,float x,float y,
    float w,float h,float alpha,GLfloat *verts,int *quads) {
  const float left=fmaxf(0.f,x),right=fminf(1.f,x+w);
  if(right<=left || alpha<=0.f)return;
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=texture;d->color[3]=alpha;
  *quads+=emit_image_rect_uv(left*screen_width,y*screen_height,(right-left)*screen_width,h*screen_height,
      (left-x)/w,0,(right-x)/w,1,verts+*quads*24);
}
static void fd_portrait(MasterLeagueRender *ui,const FrontdoorView *v,
    float x,float y,float h,GLfloat *verts,int *quads) {
  const float w=h*.75f*screen_height/screen_width;
  const uint32_t indices[]={v->portrait_previous%4u,v->portrait_current%4u};
  for(uint32_t i=0;i<2u;i++) {
    const float a=i ? v->portrait_mix : 1.f-v->portrait_mix;
    if(a<=0.f)continue;
    const float direction=(v->portrait_current&1u) ? -1.f : 1.f;
    const float offset=v->portrait_previous==v->portrait_current ? 0.f :
        direction*.285f*(i ? 1.f-v->portrait_mix : -v->portrait_mix);
    fd_sliding_image(ui,gl.main_menu_portrait_tex[indices[i]],x+offset,y,w,h,a,verts,quads);
  }
}
/* Independent flat vector ribbons: no new texture, decoding or render target.
 * Their positions morph with the exact portrait transition and drift at rest. */
static void fd_corner_band(MasterLeagueRender *ui,float offset,float width,int bottom,
    int red,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,0);if(!d)return;
  d->color[0]=red ? .92f : .025f;d->color[1]=red ? .16f : .35f;d->color[2]=red ? .23f : .87f;
  const float ratio=screen_width/(float)screen_height;
  const float xy[4][2]={{offset,0},{offset+width,0},{0,(offset+width)*ratio},{0,offset*ratio}};
  static const uint32_t order[]={0,1,2,0,2,3};
  GLfloat *out=verts+*quads*24;
  for(uint32_t i=0;i<6u;i++) {
    float x=xy[order[i]][0],y=xy[order[i]][1];
    if(bottom){x=1.f-x;y=1.f-y;}
    out[i*4]=x*2.f-1.f;out[i*4+1]=1.f-y*2.f;out[i*4+2]=out[i*4+3]=0;
  }
  (*quads)++;
}
static void fd_background(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_rect(ui,0,0,1,1,.94f,.965f,.985f,verts,quads);
  ml_ui_image(ui,gl.frontdoor_flat_tex,0,0,0,1,1,verts,quads);
  static const float positions[]={.075f,.125f,.092f,.052f};
  const float t=fmaxf(0.f,fminf(1.f,v->portrait_mix));
  const float pose=positions[v->portrait_previous%4u]*(1.f-t)+positions[v->portrait_current%4u]*t;
  const float drift=sinf(v->motion_phase*6.2831853f)*.008f;
  for(uint32_t corner=0;corner<2;corner++) {
    const float p=pose+(corner ? -drift : drift);
    fd_corner_band(ui,p,.017f,corner,0,verts,quads);
    fd_corner_band(ui,p+.042f,.0035f,corner,1,verts,quads);
  }
}
static void fd_title(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  /* Unframed cover composition: the player and the wordmark share one world. */
  fd_portrait(ui,v,.533f,.018f,.982f,verts,quads);
  fd_brand(ui,.058f,.235f,.397f,verts,quads);
  fd_rect(ui,.061f,.552f,.043f,.006f,.03f,.34f,.94f,verts,quads);
  fd_rect(ui,.110f,.552f,.022f,.006f,.90f,.09f,.21f,verts,quads);
  fd_card(ui,.059f,.644f,.344f,.102f,1,0,verts,quads);
  const float cy=.695f,ih=.053f,iw=ih*screen_height/screen_width;
  const char *label="PRESS A TO START";
  const float th=.0375f,tw=measure_efootball_line_mode(label,16,th*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width;
  const float x=.059f+(.344f-(iw+.015f+tw))*.5f;
  ml_ui_image(ui,switch_button_texture("A"),0,x,cy-ih*.5f,iw,ih,verts,quads);
  fd_text(ui,label,x+iw+.015f,fd_cap_top(cy,th),tw+.003f,th,-1,verts,quads);
  fd_text(ui,"ANDROSWITCH PROJECT 2026",.059f,.940f,.44f,.0236f,-3,verts,quads);
}
static void fd_menu(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  static const char *const labels[]={"MATCH","MODES","SETTINGS","CREDITS"};
  static const uint32_t icons[]={ML_HEADER_MATCH,ML_HEADER_TROPHY,ML_HEADER_SETTINGS,ML_HEADER_MESSAGES};
  fd_portrait(ui,v,.560f,.013f,.899f,verts,quads);
  fd_brand(ui,.050f,.063f,.286f,verts,quads);
  /* A 2.17x active tile and compact neighbours share a fixed-height rail.
   * Icons/text grow gently with the row; native focus changes immediately. */
  float y=.337f;
  for(uint32_t i=0;i<4u;i++) {
    const float amount=fmaxf(0.f,fminf(1.f,v->menu_weights[i]));
    const float x=.050f,w=.407f,h=.084f+.098f*amount;const int selected=v->focus==i;
    fd_card(ui,x,y,w,h,selected,0,verts,quads);
    if(selected)fd_menu_pattern_loop(ui,v->menu_pattern_phase,verts);
    const float ih=.046f+.028f*amount,th=.0347f+.007f*amount,cy=y+h*.5f;
    ml_ui_header_icon(ui,icons[i],x+.027f,cy-ih*.5f,ih,verts,quads);
    fd_text(ui,labels[i],x+.084f,fd_cap_top(cy,th),w-.110f,th,selected ? -1 : -2,verts,quads);
    y+=h+.020f;
  }
}
static void fd_match_menu(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  const int modes=v->page==FD_MODES;
  FrontdoorView hero=*v;hero.portrait_previous=hero.portrait_current=v->focus%4u;hero.portrait_mix=1;
  fd_portrait(ui,&hero,.564f,.041f,.871f,verts,quads);
  fd_text(ui,modes ? "GAME MODES" : "MATCH",.045f,.074f,.49f,.0583f,-2,verts,quads);
  fd_text(ui,modes ? "CHOOSE YOUR COMPETITION" : "CHOOSE HOW YOU PLAY",.047f,.159f,.49f,.0264f,-3,verts,quads);
  static const char *const match_detail[]={"Play against the computer","Go head-to-head on one console"};
  static const char *const mode_detail[]={"The road to the final","Build your season, chase the title","Your club. Your career."};
  static const uint32_t mode_icon[]={ML_HEADER_TROPHY,ML_HEADER_RANKING,ML_HEADER_MANAGER};
  const float height=modes ? .176f : .222f;
  const float start=modes ? .243f : .288f;
  for(uint32_t i=0;i<v->row_count && i<3u;i++) {
    const float y=start+i*(height+.020f);const int selected=v->focus==i;
    fd_card(ui,.035f,y,.53f,height,selected,i==1u,verts,quads);
    ml_ui_header_icon(ui,modes ? mode_icon[i] : i ? ML_HEADER_SQUAD : ML_HEADER_MATCH,.059f,y+.050f,.075f,verts,quads);
    fd_text(ui,v->rows[i].label,.123f,y+.039f,.408f,.045f,selected ? -1 : -2,verts,quads);
    fd_text(ui,modes ? mode_detail[i] : match_detail[i],.123f,y+.112f,.413f,.0278f,selected ? -1 : -3,verts,quads);
  }
  if(v->status[0])fd_text(ui,v->status,.04f,.865f,.90f,.0264f,-2,verts,quads);
}
static void fd_stars(MasterLeagueRender *ui,uint32_t grade,float x,float y,GLfloat *verts,int *quads) {
  /* Native star alpha, including half grades. The canvas is a true square. */
  const float h=.026f,w=h*screen_height/screen_width;
  for(uint32_t i=0;i<5u;i++) {
    ml_ui_image(ui,gl.team_rating_star_tex,0,x+i*(w+.004f),y,w,h,verts,quads);
    ui->draws[ui->draw_count-1u].kind=3;
    ui->draws[ui->draw_count-1u].color[3]=.20f;
    const float part=grade>=i*2u+2u ? 1.f : grade==i*2u+1u ? .5f : 0.f;
    if(part>0) {
      MlDraw *d=ml_ui_draw(ui,*quads,3);if(!d)return;d->texture=gl.team_rating_star_tex;
      d->color[0]=1.f;d->color[1]=.85f;d->color[2]=.32f;
      *quads+=emit_image_rect_uv((x+i*(w+.004f))*screen_width,y*screen_height,w*part*screen_width,h*screen_height,0,0,part,1,verts+*quads*24);
    }
  }
}
static void fd_selector(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_header(ui,"SELECT TEAMS",v->side_count==1 ? "CHOOSE A TEAM FOR THIS SLOT" : v->exhibition ? "EXHIBITION / HOME & AWAY" : "LOCAL MATCH / PLAYER 1 & PLAYER 2",ML_HEADER_SQUAD,verts,quads);
  for(uint32_t side=0;side<v->side_count && side<2u;side++) {
    const FrontdoorSide *s=&v->sides[side];
    const float x=v->side_count==1 ? .275f : side ? .525f : .035f,w=.44f;
    fd_card(ui,x,.195f,w,.666f,0,0,verts,quads);
    fd_art(ui,side ? 1 : 0,x,.195f,w,.073f,verts,quads);
    fd_text(ui,s->owner,x+.016f,.216f,.145f,.0278f,-1,verts,quads);
    fd_text(ui,s->title,x+.164f,.219f,.26f,.025f,-1,verts,quads);
    if(!s->ready)for(uint32_t i=0;i<s->neighbour_count && i<4u;i++) {
      const FrontdoorRow *row=&s->neighbours[i];
      const float y=row->relative<0 ? .286f+(row->relative+2)*.063f : .708f+(row->relative-1)*.063f;
      fd_rect(ui,x+.012f,y,w-.024f,.056f,.935f,.958f,.981f,verts,quads);
      ml_ui_image(ui,gl.badge_tex,row->badge,x+.022f,y+.006f,.0248f,.044f,verts,quads);
      fd_text(ui,row->label,x+.059f,y+.016f,w-.090f,.025f,-2,verts,quads);
    }
    const float cy=.421f-(s->ready ? .126f*s->ready_mix : 0.f);
    fd_card(ui,x+.012f,cy,w-.024f,.267f,s->active || s->ready,side,verts,quads);
    /* Both featured teams keep their side colour. Only the owning side gets
     * the outside focus ring; inactive never turns into an all-white card. */
    fd_art(ui,side ? 1 : 0,x+.014f,cy+.0035f,w-.028f,.260f,verts,quads);
    const int ink=-1;
    fd_text(ui,s->name,x+.030f,cy+.018f,w-.060f,.0347f,ink,verts,quads);
    ml_ui_image(ui,gl.badge_tex,s->badge,x+.034f,cy+.084f,.0844f,.15f,verts,quads);
    if(s->phase==PES_2P_TEAM_SELECTOR_PHASE_TEAM && s->stats_valid) {
      static const char *const positions[]={"FW","MF","DF"};
      for(uint32_t j=0;j<3u;j++) {
        const float y=cy+.084f+j*.05f;char value[16];snprintf(value,sizeof(value),"%u",s->ratings[j]);
        fd_text(ui,positions[j],x+.150f,y,.038f,.025f,ink,verts,quads);
        fd_text(ui,value,x+.374f,y,.035f,.025f,ink,verts,quads);
        fd_rect(ui,x+.196f,y+.009f,.163f,.009f,.65f,.74f,.83f,verts,quads);
        float fraction=fminf(1.f,s->ratings[j]/100.f);
        if(fraction>0)fd_rect(ui,x+.196f,y+.009f,.163f*fraction,.009f,
            ink==-1 ? 1.f : .05f,ink==-1 ? 1.f : .36f,ink==-1 ? 1.f : .73f,verts,quads);
      }
      fd_stars(ui,s->grade,x+.151f,cy+.234f,verts,quads);
    }else if(s->phase==PES_2P_TEAM_SELECTOR_PHASE_TEAM) {
      fd_text(ui,"RATINGS UNAVAILABLE",x+.151f,cy+.128f,.255f,.0264f,ink,verts,quads);
    }else {
      fd_text(ui,"LEAGUE / REGION",x+.151f,cy+.105f,.255f,.0264f,ink,verts,quads);
      fd_text(ui,"CONFIRM TO VIEW TEAMS",x+.151f,cy+.164f,.255f,.0236f,ink,verts,quads);
    }
    if(s->ready) {
      fd_rect(ui,x+.012f,cy+.290f,w-.024f,.077f,.91f,.96f,.99f,verts,quads);
      ml_ui_center_text(ui,"READY",x+.012f,cy+.290f,w-.024f,.077f,.036f,0,-2,verts,quads);
    }
  }
  if(v->side_count==2)ml_ui_center_text(ui,"VS",.478f,.476f,.045f,.08f,.036f,0,-2,verts,quads);
}
static void fd_hub(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_header(ui,"MATCH HUB",v->subtitle,ML_HEADER_MATCH,verts,quads);
  for(uint32_t side=0;side<2u;side++) {
    const FrontdoorSide *s=&v->sides[side];const float x=side ? .525f : .035f;
    fd_card(ui,x,.208f,.44f,.536f,0,0,verts,quads);
    fd_art(ui,side,x,.208f,.44f,.077f,verts,quads);
    fd_text(ui,s->name,x+.016f,.232f,.408f,.0347f,-1,verts,quads);
    ml_ui_image(ui,gl.badge_tex,s->badge,x+.025f,.360f,.0844f,.15f,verts,quads);
    ml_ui_center_text(ui,s->owner,x+.012f,.534f,.11f,.044f,.0278f,0,-2,verts,quads);
    fd_text(ui,"STARTING XI",x+.151f,.305f,.268f,.0236f,-3,verts,quads);
    for(uint32_t i=0;i<s->lineup_count && i<11u;i++) {
      const float y=.348f+i*.0341f;
      if(!(i&1u))fd_rect(ui,x+.141f,y-.003f,.282f,.0333f,.94f,.963f,.982f,verts,quads);
      char num[8];snprintf(num,sizeof(num),"%02u",i+1u);
      fd_text(ui,num,x+.150f,y+.003f,.025f,.0236f,-3,verts,quads);
      fd_text(ui,s->lineup[i],x+.187f,y+.003f,.227f,.025f,-2,verts,quads);
    }
    if(!s->lineup_count)fd_text(ui,"OPEN GAME PLAN",x+.151f,.383f,.26f,.0278f,-3,verts,quads);
  }
  ml_ui_center_text(ui,"VS",.478f,.422f,.045f,.08f,.036f,0,-2,verts,quads);
  static const char *const labels[]={"STADIUM","KITS","KICK OFF","GAME PLAN","GENERAL SETTINGS"};
  static const uint32_t icons[]={ML_HEADER_MATCH,ML_HEADER_SQUAD,ML_HEADER_MATCH,ML_HEADER_TACTICS,ML_HEADER_SETTINGS};
  const uint32_t count=v->action_count ? v->action_count : 5u;
  const float gap=.012f,w=(.93f-(count-1u)*gap)/count;
  for(uint32_t i=0;i<count && i<5u;i++) {
    const float x=.035f+i*(w+gap);const int selected=v->focus==i;
    fd_card(ui,x,.784f,w,.100f,selected,0,verts,quads);
    fd_action_content(ui,labels[i],icons[i],x,.784f,w,.100f,i==4u ? .0222f : .0264f,selected ? -1 : -2,verts,quads);
  }
}
static void fd_kits(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_header(ui,"SELECT KITS","MATCH HUB / HOME & AWAY UNIFORMS",ML_HEADER_SQUAD,verts,quads);
  for(uint32_t side=0;side<2u;side++) {
    const float x=side ? .525f : .035f;const FrontdoorSide *s=&v->sides[side];const int selected=v->focus==side;
    if(selected && !v->kit_editing) {
      fd_rect(ui,x-.004f,.213f,.448f,.632f,side ? .89f : .02f,side ? .12f : .43f,side ? .20f : .86f,verts,quads);
    }
    fd_card(ui,x,.219f,.44f,.62f,0,side,verts,quads);
    fd_art(ui,side,x,.219f,.44f,.080f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,s->badge,x+.016f,.232f,.029f,.052f,verts,quads);
    fd_text(ui,s->name,x+.060f,.243f,.362f,.0306f,-1,verts,quads);
    if(gl.native_uniform_valid_mask&(1u<<side)) {
      const float aspect=gl.native_uniform_height>0 ? (float)gl.native_uniform_width/gl.native_uniform_height : 1.f;
      const float h=.344f,w=fminf(.37f,h*screen_height/screen_width*aspect);
      ml_ui_image(ui,gl.native_uniform_texture[side],0,x+(.44f-w)*.5f,.342f,w,h,verts,quads);
    }else {
      ml_ui_header_icon(ui,ML_HEADER_SQUAD,x+.18f,.427f,.14f,verts,quads);
      ml_ui_center_text(ui,"KIT PREVIEW UNAVAILABLE",x+.018f,.618f,.404f,.04f,.025f,0,-3,verts,quads);
    }
    fd_card(ui,x+.015f,.727f,.410f,.087f,selected && v->kit_editing,side,verts,quads);
    char value[72];
    if(s->kit_count)snprintf(value,sizeof(value),"KIT %u",s->kit_number);
    else fd_copy(value,sizeof(value),"NO KIT AVAILABLE");
    fd_rect(ui,x+.069f,.739f,.302f,.063f,.95f,.975f,1.f,verts,quads);
    fd_center_text(ui,value,x+.112f,.7705f,.216f,.0306f,-2,verts,quads);
    if(s->kit_count>1u && selected && v->kit_editing) {
      ml_ui_icon(ui,0,x+.077f,.7485f,.044f,verts,quads);
      ml_ui_icon(ui,1,x+.338f,.7485f,.044f,verts,quads);
    }
  }
}
static void fd_settings(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_header(ui,v->page==FD_STADIUM ? "STADIUM" : v->title[0] ? v->title : "GENERAL SETTINGS",
      v->page==FD_VIDEO ? "DISPLAY / PERFORMANCE" : v->page==FD_PAUSE_SETTINGS ? "PAUSE / MATCH PREFERENCES" : "MATCH HUB / MATCH PREFERENCES",ML_HEADER_SETTINGS,verts,quads);
  const float h=.032f+v->row_count*.09f,y=.20f+(.664f-h)*.5f;
  fd_card(ui,.11f,y,.78f,h,0,0,verts,quads);
  for(uint32_t i=0;i<v->row_count && i<6u;i++) {
    const float yy=y+.021f+i*.09f;const int selected=v->focus==v->first_row+i;
    fd_card(ui,.126f,yy,.748f,.077f,selected,0,verts,quads);
    fd_text(ui,v->rows[i].label,.146f,fd_cap_top(yy+.0385f,.0306f),.429f,.0306f,selected ? -1 : -2,verts,quads);
    fd_rect(ui,.596f,yy+.008f,.263f,.061f,.95f,.975f,1.f,verts,quads);
    ml_ui_icon(ui,0,.603f,yy+.0165f,.044f,verts,quads);
    ml_ui_icon(ui,1,.827f,yy+.0165f,.044f,verts,quads);
    fd_center_text(ui,v->rows[i].value,.641f,yy+.0385f,.173f,.0306f,-2,verts,quads);
  }
  if(v->total_rows>v->row_count) {
    const float track=v->row_count*.09f-.020f,thumb=track*v->row_count/v->total_rows;
    fd_rect(ui,.881f,y+.021f,.003f,track,.83f,.87f,.93f,verts,quads);
    fd_rect(ui,.881f,y+.021f+(track-thumb)*v->first_row/(v->total_rows-v->row_count),.003f,thumb,.04f,.36f,.80f,verts,quads);
  }
}
static void fd_info(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_header(ui,v->title[0] ? v->title : "CREDITS","FOOTBALLNX / ANDROSWITCH PROJECT",ML_HEADER_MESSAGES,verts,quads);
  fd_card(ui,.16f,.244f,.68f,.578f,0,0,verts,quads);
  fd_brand(ui,.34f,.295f,.32f,verts,quads);
  for(uint32_t i=0;i<v->row_count && i<6u;i++)
    fd_center_text(ui,v->rows[i].label,.20f,.545f+i*.048f,.60f,.0306f,i ? -3 : -2,verts,quads);
}
static void fd_loading(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_brand(ui,.043f,.058f,.185f,verts,quads);
  if(v->page==FD_VS) {
    for(uint32_t side=0;side<2u;side++) {
      const float x=side ? .565f : .135f;
      fd_card(ui,x,.285f,.30f,.398f,0,side,verts,quads);
      fd_art(ui,side,x,.285f,.30f,.025f,verts,quads);
      const float bh=.22f,bw=bh*screen_height/screen_width;
      ml_ui_image(ui,gl.badge_tex,v->sides[side].badge,x+(.30f-bw)*.5f,.337f,bw,bh,verts,quads);
      fd_center_text(ui,v->sides[side].name,x+.016f,.625f,.268f,.031f,-2,verts,quads);
    }
    fd_center_text(ui,"VS",.455f,.474f,.09f,.054f,-2,verts,quads);
  }
  fd_text(ui,"LOADING",.825f,fd_cap_top(.91f,.0278f),.10f,.0278f,-2,verts,quads);
  for(uint32_t i=0;i<8u;i++) {
    const float angle=(v->motion_phase*6.f+i/8.f)*6.2831853f;
    const float size=.006f,sw=size*screen_height/screen_width;
    const float x=.95f+cosf(angle)*.014f*screen_height/screen_width;
    const float y=.91f+sinf(angle)*.014f;
    ml_ui_rect(ui,x-sw*.5f,y-size*.5f,sw,size,.03f,.35f,.88f,.25f+.75f*i/7.f,-1,0,1,verts,quads);
  }
}
static void fd_match_stats(MasterLeagueRender *ui,const FrontdoorView *v,
    const char *heading,GLfloat *verts,int *quads) {
  fd_center_text(ui,heading,.35f,.058f,.30f,.036f,-2,verts,quads);
  for(uint32_t side=0;side<2u;side++) {
    const float x=side ? .52f : .035f;
    fd_art(ui,side,x,.104f,.445f,.135f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,v->sides[side].badge,x+.014f,.116f,.063f,.112f,verts,quads);
    fd_text(ui,v->sides[side].name,x+.088f,fd_cap_top(.1715f,.0306f),.27f,.0306f,-1,verts,quads);
    fd_center_text(ui,v->score[side],x+.360f,.1715f,.073f,.064f,-1,verts,quads);
  }
  fd_card(ui,.17f,.274f,.66f,.455f,0,0,verts,quads);
  fd_center_text(ui,"MATCH STATS",.34f,.310f,.32f,.0306f,-2,verts,quads);
  static const char *const labels[]={"POSSESSION","SHOTS","FOULS","CORNER KICKS","FREE KICKS","PASSES","TACKLES","SAVES"};
  for(uint32_t row=0;row<8u;row++) {
    const float y=.345f+row*.045f;
    if(!(row&1u))fd_rect(ui,.184f,y,.632f,.043f,.938f,.96f,.982f,verts,quads);
    fd_center_text(ui,labels[row],.32f,y+.0215f,.36f,.025f,-3,verts,quads);
    for(uint32_t side=0;side<2u;side++)fd_center_text(ui,v->stats[side][row],side ? .713f : .207f,y+.0215f,.08f,.028f,-2,verts,quads);
  }
}
static void fd_pause(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_match_stats(ui,v,"PAUSE MENU",verts,quads);
  static const char *const labels_action[]={"GAME PLAN","GENERAL SETTINGS","CAMERA SETTINGS","TOP MENU"};
  static const uint32_t icons[]={ML_HEADER_TACTICS,ML_HEADER_SETTINGS,ML_HEADER_SETTINGS,ML_HEADER_NEWS};
  for(uint32_t i=0;i<4u;i++) {
    const float x=.035f+i*.2375f;
    fd_card(ui,x,.778f,.2175f,.107f,v->focus==i,0,verts,quads);
    fd_action_content(ui,labels_action[i],icons[i],x,.778f,.2175f,.107f,.025f,v->focus==i ? -1 : -2,verts,quads);
  }
}
static void fd_result(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  fd_match_stats(ui,v,v->title,verts,quads);
  const uint32_t count=v->action_count<3u ? v->action_count : 3u;
  const float width=.296f,gap=.021f;
  const float start=(1.f-count*width-(count ? count-1u : 0u)*gap)*.5f;
  for(uint32_t i=0;i<count;i++) {
    const float x=start+i*(width+gap);
    const char *label=v->rows[i].label;
    const uint32_t icon=!strcmp(label,"GAME PLAN") ? ML_HEADER_TACTICS :
        (!strncmp(label,"BACK TO ",8) || !strcmp(label,"TOP TO MENU")) ? ML_HEADER_NEWS : ML_HEADER_MATCH;
    fd_card(ui,x,.778f,width,.107f,v->focus==i,0,verts,quads);
    fd_action_content(ui,label,icon,x,.778f,width,.107f,.026f,v->focus==i ? -1 : -2,verts,quads);
  }
}
static void fd_confirm(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,0,0,1,1,.018f,.05f,.14f,.57f,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1].round.radius=0;
  fd_card(ui,.21f,.27f,.58f,.425f,0,0,verts,quads);
  fd_art(ui,2,.21f,.27f,.58f,.09f,verts,quads);
  fd_center_text(ui,"RETURN TO TOP MENU?",.24f,.315f,.52f,.038f,-1,verts,quads);
  fd_center_text(ui,"UNFINISHED MATCH PROGRESS WILL BE LOST.",.235f,.445f,.53f,.028f,-2,verts,quads);
  for(uint32_t i=0;i<2u;i++) {
    const float x=.245f+i*.267f;
    fd_card(ui,x,.563f,.243f,.087f,v->confirm_focus==i,0,verts,quads);
    fd_center_text(ui,i ? "CANCEL" : "CONFIRM",x,.6065f,.243f,.0306f,v->confirm_focus==i ? -1 : -2,verts,quads);
  }
}
static void frontdoor_emit(MasterLeagueRender *ui,const FrontdoorView *v,GLfloat *verts,int *quads) {
  memset(ui,0,sizeof(*ui));
  fd_background(ui,v,verts,quads);
  switch(v->page) {
    case FD_TITLE:fd_title(ui,v,verts,quads);break;
    case FD_MENU:fd_menu(ui,v,verts,quads);break;
    case FD_MATCH:case FD_MODES:fd_match_menu(ui,v,verts,quads);break;
    case FD_SELECTOR:fd_selector(ui,v,verts,quads);break;
    case FD_HUB:fd_hub(ui,v,verts,quads);break;
    case FD_KITS:fd_kits(ui,v,verts,quads);break;
    case FD_STADIUM:case FD_SETTINGS:case FD_VIDEO:case FD_PAUSE_SETTINGS:fd_settings(ui,v,verts,quads);break;
    case FD_INFO:fd_info(ui,v,verts,quads);break;
    case FD_LOADING:case FD_VS:fd_loading(ui,v,verts,quads);break;
    case FD_PAUSE:fd_pause(ui,v,verts,quads);break;
    case FD_RESULT:fd_result(ui,v,verts,quads);break;
    default:break;
  }
  fd_footer(ui,v,verts,quads);
  if(v->confirm)fd_confirm(ui,v,verts,quads);
}
