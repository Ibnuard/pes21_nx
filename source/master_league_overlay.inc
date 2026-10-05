/* Renderer-only adapter. State, navigation, saves and transactions live in
 * master_league_frontend.c. Reuses the shared high-resolution font/badge
 * pipeline, FNX button palette, rounded shader and Switch helper sprites. */
typedef struct {
  int first, count, kind, theme, selected, enabled;
  GLuint texture;
  float color[4];
  float uv[4];
  RoundedRectStyle round;
} MlDraw;
typedef struct {
  MlView view;
  MlDraw draws[224];
  uint32_t draw_count;
  float helper_centers[4];
  float shoulder_y;
  int shoulders;
} MasterLeagueRender;

static MlDraw *ml_ui_draw(MasterLeagueRender *ui, int first, int kind) {
  if (ui->draw_count >= 224u) return NULL;
  MlDraw *d=&ui->draws[ui->draw_count++];
  memset(d,0,sizeof(*d)); d->first=first; d->count=1; d->kind=kind; d->theme=-1;
  for (uint32_t i=0;i<4u;i++) d->color[i]=1.0f;
  return d;
}
static void ml_ui_rect(MasterLeagueRender *ui, float x,float y,float w,float h,
    float r,float g,float b,float a, int theme,int selected,int enabled,
    GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,0); if (!d) return;
  d->color[0]=r;d->color[1]=g;d->color[2]=b;d->color[3]=a;
  d->theme=theme;d->selected=selected;d->enabled=enabled;
  d->round=(RoundedRectStyle){w*screen_width,h*screen_height,fminf(h*0.22f,0.012f)*screen_height};
  *quads+=emit_round_rect_quad(x*screen_width,y*screen_height,
      d->round.width,d->round.height,verts+*quads*24);
}
static void ml_ui_text(MasterLeagueRender *ui,const char *text,float x,float y,
    float width,float height,int stencil,int theme,int selected,int enabled,
    GLfloat *verts,int *quads) {
  if (!text || !text[0]) return;
  char line[112];snprintf(line,sizeof(line),"%s",text);
  const uint32_t weight=stencil ? EFOOTBALL_FONT_STENCIL : EFOOTBALL_FONT_BOLD;
  const float gh=height*screen_height, maxw=width*screen_width;
  size_t length=strlen(line);
  if (measure_efootball_line_mode(line,(int)length,gh,weight,0)>maxw) {
    while (length>3u && measure_efootball_line_mode(line,(int)length,gh,weight,0)>maxw) {
      length--; line[length]=0;
      if (length>3u) memcpy(line+length-3u,"...",3u);
    }
  }
  MlDraw *d=ml_ui_draw(ui,*quads,1);if(!d)return;
  d->theme=theme;d->selected=selected;d->enabled=enabled;
  if(theme==-2 || theme==-3) {
    d->color[0]=theme==-2 ? .025f : .27f;
    d->color[1]=theme==-2 ? .10f : .36f;
    d->color[2]=theme==-2 ? .29f : .48f;
  }
  *quads+=emit_efootball_line_mode(line,(int)length,x*screen_width,y*screen_height,
      gh,weight,0,verts+*quads*24);
  d->count=*quads-d->first;
}
static void ml_ui_image(MasterLeagueRender *ui, GLuint tex, uint32_t badge,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=badge ? gl.badge_tex : tex;
  if (badge) *quads+=emit_badge(badge,x*screen_width,y*screen_height,w*screen_width,h*screen_height,verts+*quads*24);
  else *quads+=emit_image_rect(x*screen_width,y*screen_height,w*screen_width,h*screen_height,verts+*quads*24);
}
static void ml_ui_button(MasterLeagueRender *ui,float x,float y,float w,float h,
    int selected,int enabled,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x-0.002f,y-0.003f,w+0.004f,h+0.006f,0,0,0,1,FNX_BUTTON_FRAME,selected,enabled,verts,quads);
  ml_ui_rect(ui,x,y,w,h,0,0,0,1,FNX_BUTTON_FILL,selected,enabled,verts,quads);
  ml_ui_rect(ui,x+0.006f,y+0.007f,w-0.012f,0.017f,0,0,0,1,FNX_BUTTON_GLOSS,selected,enabled,verts,quads);
}
/* All four decorative sprites share one high-resolution texture. UV gutters
 * exclude adjacent artwork and rounding happens in the shader, not the PNG.
 * Text and official badges are always separate native-resolution geometry. */
static void ml_ui_art(MasterLeagueRender *ui,uint32_t sprite,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=gl.master_league_cards_tex;
  const float aspect=w*screen_width/(h*screen_height);
  const float uw=aspect<2.f ? .496f*aspect/2.f : .496f;
  const float vh=aspect>2.f ? .496f*2.f/aspect : .496f;
  const float u=(sprite%2u)*.5f+.002f+(.496f-uw)*.5f;
  const float v=(sprite/2u)*.5f+.002f+(.496f-vh)*.5f;
  d->uv[0]=u;d->uv[1]=v;d->uv[2]=uw;d->uv[3]=vh;
  d->round=(RoundedRectStyle){w*screen_width,h*screen_height,9.f};
  *quads+=emit_image_rect_uv(x*screen_width,y*screen_height,w*screen_width,h*screen_height,
      u,v,u+uw,v+vh,verts+*quads*24);
}
static void ml_ui_frame(MasterLeagueRender *ui,float x,float y,float w,float h,
    int selected,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x,y+.005f,w,h,.04f,.12f,.28f,.12f,-1,0,1,verts,quads);
  if(selected) {
    ml_ui_rect(ui,x-.005f,y-.008f,w+.010f,h+.016f,.64f,1.f,.22f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,x-.0025f,y-.004f,w+.005f,h+.008f,0,.68f,.92f,1,-1,0,1,verts,quads);
  }
}
static void ml_ui_panel(MasterLeagueRender *ui,const char *title,
    float x,float y,float w,float h,int selected,GLfloat *verts,int *quads) {
  ml_ui_frame(ui,x,y,w,h,selected,verts,quads);
  ml_ui_rect(ui,x,y,w,h,1,1,1,.98f,-1,0,1,verts,quads);
  ml_ui_rect(ui,x,y,w,.054f,.02f,.18f,.47f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,title,x+.016f,y+.014f,w-.032f,.028f,0,-1,0,1,verts,quads);
}
static void ml_ui_minirows(MasterLeagueRender *ui,const MlViewRow *rows,uint32_t count,
    float x,float y,float w,int rank,GLfloat *verts,int *quads) {
  for(uint32_t i=0;i<count && i<3u;i++) {
    const MlViewRow *r=&rows[i];const float yy=y+i*.067f;
    if(i%2u==0u) ml_ui_rect(ui,x,yy-.005f,w,.061f,.92f,.95f,.99f,1,-1,0,1,verts,quads);
    if(rank) ml_ui_text(ui,r->detail,x+.009f,yy+.013f,.026f,.0278f,0,-2,0,1,verts,quads);
    const float bx=x+(rank ? .039f : .010f);
    if(r->badge) ml_ui_image(ui,gl.badge_tex,r->badge,bx,yy+.002f,.0293f,.052f,verts,quads);
    const float tx=bx+(r->badge ? .037f : .004f);
    ml_ui_text(ui,r->label,tx,yy+(rank ? .014f : .002f),w-(tx-x)-.047f,.0264f,0,-2,0,1,verts,quads);
    if(!rank) ml_ui_text(ui,r->detail,tx,yy+.034f,w-(tx-x)-.006f,.021f,0,-3,0,1,verts,quads);
    ml_ui_text(ui,r->value,x+w-.040f,yy+.014f,.035f,.0264f,0,-2,0,1,verts,quads);
  }
}
static void ml_ui_feature(MasterLeagueRender *ui,const MlView *v,uint32_t item,
    uint32_t art,float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const MlViewRow *r=&v->rows[item];const int selected=v->selected==item && r->enabled;
  ml_ui_frame(ui,x,y,w,h,selected,verts,quads);
  ml_ui_art(ui,art,x,y,w,h,verts,quads);
  ml_ui_text(ui,r->label,x+.021f,y+.027f,w-.04f,.0347f,0,-1,0,1,verts,quads);
  if(v->section==0u && item==0u && v->next.home[0]) {
    ml_ui_image(ui,gl.badge_tex,v->next.home_badge,x+w*.23f-.022f,y+.065f,.044f,.0782f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,v->next.away_badge,x+w*.77f-.022f,y+.065f,.044f,.0782f,verts,quads);
    ml_ui_text(ui,"VS",x+w*.47f,y+.105f,.04f,.030f,0,-1,0,1,verts,quads);
    ml_ui_text(ui,v->next.home,x+.020f,y+.150f,w*.42f,.025f,0,-1,0,1,verts,quads);
    ml_ui_text(ui,v->next.away,x+w*.55f,y+.150f,w*.41f,.025f,0,-1,0,1,verts,quads);
    char match[112];snprintf(match,sizeof(match),"%s  /  %.65s",v->next.day,v->next.competition);
    ml_ui_text(ui,match,x+.021f,y+.188f,w-.04f,.021f,0,-1,0,1,verts,quads);
  } else {
    ml_ui_text(ui,r->detail,x+.021f,y+.092f,w-.05f,.025f,0,-1,0,1,verts,quads);
    char value[80];
    if(v->section==0u && item==1u) snprintf(value,sizeof(value),"4 STORIES  /  OPEN CLUB CAROUSEL");
    else if(v->section==1u && item==0u) snprintf(value,sizeof(value),"%u REGISTERED PLAYERS",v->squad_size);
    else if(v->section==2u && item==0u) snprintf(value,sizeof(value),"TRANSFER BALANCE  %s",v->balance);
    else if(v->section==3u && item==0u) snprintf(value,sizeof(value),"YOUR POSITION  %u",v->rank);
    else snprintf(value,sizeof(value),"%s",r->value[0] ? r->value : "VIEW DETAILS");
    ml_ui_text(ui,value,x+.021f,y+.170f,w-.05f,.025f,0,-1,0,1,verts,quads);
  }
}
static void master_league_emit(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  memset(ui,0,sizeof(*ui)); ml_frontend_view(&ui->view);
  MlView *v=&ui->view;
  static uint32_t last_serial;
  static uint64_t slide_tick;
  if (last_serial!=v->navigation_serial) {
    last_serial=v->navigation_serial;slide_tick=armGetSystemTick();
  }
  const float elapsed=(float)armTicksToNs(armGetSystemTick()-slide_tick)/180000000.0f;
  const float t=elapsed<1.0f ? 1.0f-elapsed : 0.0f;
  const float slide=0.075f*t*t*t*v->slide_direction;
  ml_ui_image(ui,gl.master_league_pearl_tex,0,0,0,1,1,verts,quads);
  ml_ui_art(ui,0,.03f,.03f,.94f,.133f,verts,quads);
  const float tx=v->badge ? .119f : .057f;
  if(v->badge) ml_ui_image(ui,gl.badge_tex,v->badge,.050f,.052f,.051f,.091f,verts,quads);
  ml_ui_text(ui,v->title,tx,.049f,.60f,.0417f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,v->caption[0] ? v->caption : "YOUR CLUB. YOUR CAREER.",tx,.112f,.70f,.025f,0,-1,0,1,verts,quads);

  if (v->page==ML_PAGE_HUB) {
    static const char *tabs[]={"HOME","SQUAD","CLUB OFFICE","COMPETITIONS"};
    for (uint32_t i=0;i<4u;i++) {
      const float x=.10f+i*.205f;
      const int selected=i==v->section;
      if(selected) ml_ui_frame(ui,x,.199f,.185f,.048f,1,verts,quads);
      ml_ui_rect(ui,x,.199f,.185f,.048f,selected ? .01f : 1.f,selected ? .36f : 1.f,selected ? .66f : 1.f,1,-1,0,1,verts,quads);
      ml_ui_text(ui,tabs[i],x+.018f,.211f,.159f,.025f,0,selected ? -1 : -2,0,1,verts,quads);
    }
    ui->shoulders=1;ui->shoulder_y=.222f;
    ml_ui_rect(ui,.049f,.204f,.034f,.038f,.03f,.18f,.45f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,.917f,.204f,.034f,.038f,.03f,.18f,.45f,1,-1,0,1,verts,quads);
    ml_ui_feature(ui,v,0,v->section==1u ? 2u : 0u,.04f+slide,.280f,.446f,.219f,verts,quads);
    ml_ui_feature(ui,v,1,v->section==2u ? 3u : 1u,.514f+slide,.280f,.446f,.219f,verts,quads);
    for(uint32_t item=2;item<4u;item++) {
      const float x=(item==2u ? .04f : .680f)+slide;
      const MlViewRow *r=&v->rows[item];
      ml_ui_panel(ui,r->label,x,.535f,.280f,.298f,v->selected==item && r->enabled,verts,quads);
      if(!v->section && item==2u) {
        ml_ui_minirows(ui,v->fixtures,v->fixture_count,x+.009f,.606f,.262f,0,verts,quads);
      } else if(!v->section && item==3u) {
        ml_ui_text(ui,v->club_name,x+.017f,.614f,.249f,.0278f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,v->season_summary,x+.017f,.667f,.249f,.025f,0,-3,0,1,verts,quads);
        ml_ui_text(ui,v->balance,x+.017f,.717f,.249f,.037f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,"CHOOSE SAVE SLOT",x+.017f,.787f,.249f,.025f,0,-3,0,1,verts,quads);
      } else {
        ml_ui_art(ui,item==2u ? 2u : 3u,x+.009f,.601f,.262f,.125f,verts,quads);
        ml_ui_text(ui,r->enabled ? "OPEN" : "UNAVAILABLE",x+.025f,.642f,.22f,.0347f,0,-1,0,1,verts,quads);
        ml_ui_text(ui,r->detail,x+.017f,.751f,.247f,.025f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,r->enabled ? "VIEW DETAILS" : "NOT IN THIS LEAGUE",x+.017f,.792f,.247f,.0236f,0,-3,0,1,verts,quads);
      }
    }
    const float cx=.338f+slide;
    ml_ui_panel(ui,v->section==1u ? "SQUAD SNAPSHOT" : v->section==2u ? "CLUB STATUS" : "LEAGUE RANKING",cx,.535f,.324f,.298f,0,verts,quads);
    if(v->section==1u) ml_ui_minirows(ui,v->squad,v->squad_count,cx+.009f,.606f,.306f,0,verts,quads);
    else if(v->section==2u) {
      char fact[64];snprintf(fact,sizeof(fact),"LEAGUE POSITION  %u",v->rank);
      ml_ui_text(ui,fact,cx+.018f,.619f,.284f,.030f,0,-2,0,1,verts,quads);
      snprintf(fact,sizeof(fact),"BOARD TARGET  TOP %u",v->board_target);
      ml_ui_text(ui,fact,cx+.018f,.680f,.284f,.025f,0,-3,0,1,verts,quads);
      ml_ui_text(ui,v->balance,cx+.018f,.742f,.284f,.0417f,0,-2,0,1,verts,quads);
    } else {
      ml_ui_text(ui,"PTS",cx+.277f,.551f,.038f,.0236f,0,-1,0,1,verts,quads);
      ml_ui_minirows(ui,v->ranking,v->ranking_count,cx+.009f,.606f,.306f,1,verts,quads);
    }
    for(uint32_t i=0;i<4u;i++) ml_ui_rect(ui,.442f+i*.032f,.864f,i==v->section ? .025f : .010f,.009f,
        .02f,i==v->section ? .43f : .57f,i==v->section ? .72f : .68f,1,-1,0,1,verts,quads);
    char indicator[64];snprintf(indicator,sizeof(indicator),"%s   %u / %u",tabs[v->section],v->section+1u,v->section_count);
    ml_ui_text(ui,indicator,.412f,.888f,.30f,.0236f,0,-2,0,1,verts,quads);
  } else if (v->page==ML_PAGE_NEWS) {
    const float x=.05f+slide;
    ml_ui_panel(ui,v->info[0],x,.218f,.90f,.60f,0,verts,quads);
    ml_ui_art(ui,v->feed_index==0u || v->feed_index==3u ? 3u : v->feed_index==1u ? 1u : 0u,x+.012f,.290f,.472f,.506f,verts,quads);
    ml_ui_text(ui,"CLUB STORIES",x+.040f,.335f,.38f,.0278f,0,-1,0,1,verts,quads);
    char number[32];snprintf(number,sizeof(number),"%02u / %02u",v->feed_index+1u,v->feed_count);
    ml_ui_text(ui,number,x+.040f,.710f,.35f,.052f,1,-1,0,1,verts,quads);
    for(uint32_t i=1;i<7u;i++) ml_ui_text(ui,v->info[i],x+.510f,.342f+(i-1u)*.068f,.36f,i==1u ? .0347f : .0278f,0,-2,0,1,verts,quads);
    for(uint32_t i=0;i<4u;i++) ml_ui_rect(ui,.436f+i*.036f,.859f,.024f,.009f,
        .02f,i==v->feed_index ? .43f : .57f,i==v->feed_index ? .72f : .68f,1,-1,0,1,verts,quads);
  } else {
    /* Five readable rows at most. Manager's two inputs intentionally retain
     * tall tiles rather than compressing them into a league settings grid. */
    ml_ui_panel(ui,v->left_title,.05f,.205f,.565f,.563f,0,verts,quads);
    ml_ui_panel(ui,v->right_title,.63f,.205f,.32f,.563f,0,verts,quads);
    const float rh=v->count<=2u ? .205f : v->count==3u ? .143f : .086f;
    for(uint32_t i=0;i<v->count;i++) {
      const MlViewRow *row=&v->rows[i];const float x=.067f,y=.278f+i*(rh+.01f);
      const int selected=!v->action_selected && v->first+i==v->selected;
      ml_ui_frame(ui,x,y,.53f,rh,selected && row->enabled,verts,quads);
      const int ink=selected && row->enabled ? -1 : row->enabled ? -2 : -3;
      if(selected && row->enabled) ml_ui_art(ui,v->page==ML_PAGE_LANDING ? i : 0u,x,y,.53f,rh,verts,quads);
      else ml_ui_rect(ui,x,y,.53f,rh,.92f,.95f,.985f,1,-1,0,1,verts,quads);
      const float logo=(row->badge || row->portrait) ? .048f : 0.f;
      if(row->badge) ml_ui_image(ui,gl.badge_tex,row->badge,x+.009f,y+(rh-.065f)*.5f,.0366f,.065f,verts,quads);
      if(row->portrait) {
        const GLuint texture=gameplan_portrait_texture(row->portrait);
        if(texture) ml_ui_image(ui,texture,0,x+.009f,y+(rh-.070f)*.5f,.0394f,.070f,verts,quads);
      }
      ml_ui_text(ui,row->label,x+.013f+logo,y+(rh>.1f ? rh*.27f : .016f),.495f-logo-(row->value[0] ? .13f : 0.f),.0292f,0,ink,selected,row->enabled,verts,quads);
      ml_ui_text(ui,row->detail,x+.013f+logo,y+(rh>.1f ? rh*.62f : .054f),.495f-logo,.025f,0,ink,selected,row->enabled,verts,quads);
      ml_ui_text(ui,row->value,x+.388f,y+(rh>.1f ? rh*.27f : .016f),.127f,.0278f,0,ink,selected,row->enabled,verts,quads);
    }
    for(uint32_t i=0;i<8u;i++) ml_ui_text(ui,v->info[i],.653f,.290f+i*.056f,.275f,.025f,0,-2,0,1,verts,quads);
    if(v->total>5u) {
      char label[40];snprintf(label,sizeof(label),"%u-%u / %u",v->first+1u,v->first+v->count,v->total);
      ml_ui_text(ui,label,.073f,.794f,.4f,.025f,0,-2,0,1,verts,quads);
    }
    for(uint32_t i=0;i<v->action_count;i++) {
      const float w=.25f,x=.5f-(v->action_count*.267f-.017f)*.5f+i*.267f;
      const int selected=v->action_selected && v->action_focus==i;
      ml_ui_button(ui,x,.812f,w,.070f,selected,v->action_enabled[i],verts,quads);
      ml_ui_text(ui,v->action[i],x+.025f,.837f,w-.05f,.029f,0,FNX_BUTTON_TEXT,selected,v->action_enabled[i],verts,quads);
    }
  }
  ml_ui_rect(ui,0,.932f,1,.068f,.025f,.10f,.28f,1,-1,0,1,verts,quads);
  if(v->status[0]) {
    ml_ui_rect(ui,.06f,.891f,.88f,.035f,.25f,.035f,.025f,.97f,-1,0,1,verts,quads);
    ml_ui_text(ui,v->status,.073f,.897f,.85f,.023f,0,-1,0,1,verts,quads);
  }
  float hx=.075f;
  for(uint32_t i=0;i<v->helper_count;i++) {
    ui->helper_centers[i]=hx;
    ml_ui_text(ui,v->helper_label[i],hx+.018f,.947f,.27f,.023f,0,-1,0,1,verts,quads);
    hx+=.235f;
  }
}

static void master_league_draw(const MasterLeagueRender *ui) {
  glUniform2f(gl.loc_off,0,0);
  for(uint32_t i=0;i<ui->draw_count;i++) {
    const MlDraw *d=&ui->draws[i];
    use_rounded_rect(d->round.width>0 ? &d->round : NULL);
    if(d->kind==2 && d->round.width>0) {
      glUniform1f(gl.loc_round_image,1.f);
      glUniform4f(gl.loc_round_uv,d->uv[0],d->uv[1],d->uv[2],d->uv[3]);
    }
    glUniform1f(gl.loc_solid,d->kind==0 ? 1.f : 0.f);
    glUniform1f(gl.loc_image,d->kind==2 ? 1.f : 0.f);
    glBindTexture(GL_TEXTURE_2D,d->kind==2 ? d->texture : d->kind==1 ? gl.efootball_tex : gl.tex);
    if(d->theme>=0) fnx_button_color((uint32_t)d->theme,d->selected,d->enabled);
    else glUniform4f(gl.loc_color,d->color[0],d->color[1],d->color[2],d->color[3]);
    glDrawArrays(GL_TRIANGLES,d->first*6,d->count*6);
  }
  use_rounded_rect(NULL);
  glBindTexture(GL_TEXTURE_2D,gl.tex);
  glUniform1f(gl.loc_image,0);glUniform1f(gl.loc_solid,1);
}
