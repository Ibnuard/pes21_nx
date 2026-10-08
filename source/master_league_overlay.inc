/* Renderer-only adapter. State, navigation, saves and transactions live in
 * master_league_frontend.c. Reuses the shared high-resolution font/badge
 * pipeline, FNX button palette, rounded shader and Switch helper sprites. */
typedef struct {
  int first, count, kind, theme, selected, enabled, layer;
  GLuint texture;
  float color[4];
  float uv[4];
  RoundedRectStyle round;
} MlDraw;
typedef struct {
  MlView view;
  MlDraw draws[384];
  uint32_t draw_count;
  float helper_centers[4];
  float shoulder_y;
  int shoulders;
} MasterLeagueRender;

static MlDraw *ml_ui_draw(MasterLeagueRender *ui, int first, int kind) {
  if (ui->draw_count >= 384u) return NULL;
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
  const uint32_t weight=stencil==2 ? EFOOTBALL_FONT_REGULAR : stencil ? EFOOTBALL_FONT_STENCIL : EFOOTBALL_FONT_BOLD;
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
  if(selected && enabled) {
    ml_ui_rect(ui,x-.004f,y-.006f,w+.008f,h+.012f,.0f,.65f,.86f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,x-.0015f,y-.0025f,w+.003f,h+.005f,1,1,1,1,-1,0,1,verts,quads);
  }
  ml_ui_rect(ui,x,y,w,h,enabled ? .025f : .76f,enabled ? (selected ? .32f : .18f) : .81f,
      enabled ? (selected ? .64f : .43f) : .87f,1,-1,0,1,verts,quads);
}
static void ml_ui_center_text(MasterLeagueRender *ui,const char *text,float x,float y,float w,float h,
    float size,int weight,int ink,GLfloat *verts,int *quads) {
  const uint32_t font=weight==2 ? EFOOTBALL_FONT_REGULAR : weight ? EFOOTBALL_FONT_STENCIL : EFOOTBALL_FONT_BOLD;
  const float tw=fminf(w-.018f,measure_efootball_line_mode(text,(int)strlen(text),size*screen_height,font,0)/screen_width);
  ml_ui_text(ui,text,x+(w-tw)*.5f,y+(h-size)*.5f,tw+.001f,size,weight,ink,0,1,verts,quads);
}
static void ml_ui_unread(MasterLeagueRender *ui,float x,float y,GLfloat *verts,int *quads) {
  /* UI notification geometry, not a replacement for the generated icons. */
  const float dot=12.f/screen_height,dw=12.f/screen_width;
  ml_ui_rect(ui,x-2.f/screen_width,y-2.f/screen_height,dw+4.f/screen_width,dot+4.f/screen_height,1,1,1,1,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=8.f;
  ml_ui_rect(ui,x,y,dw,dot,.91f,.08f,.18f,1,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=6.f;
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
static void ml_ui_icon(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float h,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;d->texture=gl.master_league_icons_tex;
  /* The handshake crosses the nominal 2x2 cell boundary. Use artwork-safe
   * bounds, not a half-texture crop that leaks its tip into the empty state. */
  const float u=sprite==3u ? .56f : (sprite%2u)*.5f,v=(sprite/2u)*.5f;
  const float uw=sprite==3u ? .44f : sprite==2u ? .53f : .5f,vh=.5f;
  const float box=h*screen_height,iw=box*fminf(1.f,uw/vh),ih=box*fminf(1.f,vh/uw);
  if(sprite==3u)d->color[3]=.58f;
  *quads+=emit_image_rect_uv(x*screen_width+(box-iw)*.5f,y*screen_height+(box-ih)*.5f,iw,ih,
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
static void ml_ui_emblem(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float h,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;d->texture=gl.master_league_emblems_tex;
  const float u=(sprite%2u)*.5f+.006f,v=(sprite/2u)*.5f+.006f;
  *quads+=emit_image_rect_uv(x*screen_width,y*screen_height,h*screen_height,h*screen_height,
    u,v,u+.488f,v+.488f,verts+*quads*24);
}
static void ml_ui_header_icon(MasterLeagueRender *ui,uint32_t icon,float x,float y,float h,GLfloat *verts,int *quads) {
  if(!icon || icon>16u)return;
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;d->texture=gl.master_league_headers_tex;
  /* Equal transparent 288x288 canvases centred around the complete symbols.
   * Keep the original artwork; sample the square, not a tight rectangular crop.
   * The matching reusable atlas regions live in header-icons-v8.json. */
  static const uint16_t bounds[16][4]={
    {28,45,316,333},{333,50,621,338},{639,50,927,338},{948,55,1236,343},
    {33,339,321,627},{333,342,621,630},{649,338,937,626},{952,337,1240,625},
    {30,630,318,918},{332,631,620,919},{635,625,923,913},{949,625,1237,913},
    {28,920,316,1208},{337,915,625,1203},{636,914,924,1202},{946,911,1234,1199}
  };
  const uint16_t *b=bounds[icon-1u];const float box=h*screen_height;
  *quads+=emit_image_rect_uv(x*screen_width,y*screen_height,box,box,
      b[0]/1254.f,b[1]/1254.f,b[2]/1254.f,b[3]/1254.f,verts+*quads*24);
}
static uint32_t ml_ui_page_icon(MlPage page) {
  switch(page) {
    case ML_PAGE_SLOTS:return ML_HEADER_SAVE;
    case ML_PAGE_SETTINGS:return ML_HEADER_SETTINGS;
    case ML_PAGE_SQUAD:case ML_PAGE_MY_TEAM:case ML_PAGE_MY_PLAYERS:return ML_HEADER_SQUAD;
    case ML_PAGE_CONTRACTS:return ML_HEADER_CONTRACT;
    case ML_PAGE_MARKET_CLUBS:case ML_PAGE_MARKET_PLAYERS:case ML_PAGE_OFFERS:return ML_HEADER_TRANSFER;
    case ML_PAGE_FINANCES:return ML_HEADER_FINANCE;
    case ML_PAGE_TABLE:return ML_HEADER_RANKING;
    case ML_PAGE_COMPETITIONS:case ML_PAGE_CUP:return ML_HEADER_TROPHY;
    case ML_PAGE_NEWS:return ML_HEADER_NEWS;
    case ML_PAGE_MESSAGES:return ML_HEADER_MESSAGES;
    case ML_PAGE_NATIONAL:case ML_PAGE_NATIONAL_OFFERS:case ML_PAGE_NATIONALITY:
    case ML_PAGE_QUALIFIERS:case ML_PAGE_INTERNATIONAL_SCHEDULE:return ML_HEADER_INTERNATIONAL;
    case ML_PAGE_NEXT:return ML_HEADER_MATCH;
    default:return ML_HEADER_MANAGER;
  }
}
static void ml_ui_panel(MasterLeagueRender *ui,const char *title,uint32_t icon,
    float x,float y,float w,float h,int selected,GLfloat *verts,int *quads) {
  ml_ui_frame(ui,x,y,w,h,selected,verts,quads);
  ml_ui_rect(ui,x,y,w,h,1,1,1,1,-1,0,1,verts,quads);
  ml_ui_rect(ui,x,y,w,.075f,.02f,.18f,.47f,1,-1,0,1,verts,quads);
  /* Square off only the bottom of the header; top corners retain the exact
   * outer card radius. Same component for landing, drawers, hub and tables. */
  ml_ui_rect(ui,x,y+.040f,w,.035f,.02f,.18f,.47f,1,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0.f;
  ml_ui_text(ui,title,x+.016f,y+.021f,w-(icon ? .078f : .032f),.0347f,0,-1,0,1,verts,quads);
  /* One 40px square centred in the 54px header at 720p: equal 7px top/bottom
   * spacing, scaling together at other resolutions. No optical Y overrides. */
  const float icon_h=40.f/720.f;
  ml_ui_header_icon(ui,icon,x+w-.015f-icon_h*screen_height/screen_width,
      y+(.075f-icon_h)*.5f,icon_h,verts,quads);
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
static void ml_ui_feed_summary(MasterLeagueRender *ui,const MlView *v,float x,float y,float w,GLfloat *verts,int *quads) {
  const MlStoryView *s=&v->story;
  ml_ui_text(ui,"CLUB FEED",x+.021f,y+.018f,w*.55f,.0347f,0,-1,0,1,verts,quads);
  const uint32_t content=ui->draw_count;
  const char *tag=v->feed_index==0u ? "MANAGER" : v->feed_index==1u ? (s->has_result ? s->result : "MATCH CENTRE") :
    v->feed_index==2u ? "SEASON WATCH" : "TRANSFER DESK";
  const float tag_w=fminf(.166f,measure_efootball_line_mode(tag,(int)strlen(tag),.0222f*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width);
  ml_ui_text(ui,tag,x+w-.021f-tag_w,y+.026f,tag_w+.001f,.0222f,0,-1,0,1,verts,quads);
  char footer[112];
  if(v->feed_index==1u && s->has_result) {
    ml_ui_image(ui,gl.badge_tex,s->home_badge,x+w*.22f-.017f,y+.067f,.034f,.0604f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,s->away_badge,x+w*.78f-.017f,y+.067f,.034f,.0604f,verts,quads);
    char score[24];snprintf(score,sizeof(score),"%u - %u",s->home_goals,s->away_goals);
    ml_ui_center_text(ui,score,x+w*.39f,y+.069f,w*.22f,.061f,.0444f,0,-1,verts,quads);
    ml_ui_center_text(ui,s->home,x+.009f,y+.132f,w*.43f,.036f,.0236f,0,-1,verts,quads);
    ml_ui_center_text(ui,s->away,x+w*.55f,y+.132f,w*.43f,.036f,.0236f,0,-1,verts,quads);
    snprintf(footer,sizeof(footer),"DAY %u / %s",s->result_day+1u,s->competition);
  }else {
    if(v->feed_index==0u)ml_ui_image(ui,gl.badge_tex,s->club_badge,x+.022f,y+.078f,.044f,.0782f,verts,quads);
    else ml_ui_header_icon(ui,v->feed_index==2u ? ML_HEADER_RANKING : v->feed_index==3u ? ML_HEADER_TRANSFER : ML_HEADER_MATCH,
      x+.014f,y+.070f,.096f,verts,quads);
    ml_ui_text(ui,v->feed_index==1u ? "NO MATCHES PLAYED YET" : s->headline,x+.087f,y+.079f,w-.110f,.0347f,0,-1,0,1,verts,quads);
    ml_ui_text(ui,v->feed_index==1u ? "Results appear after play or simulate" : s->summary,x+.087f,y+.131f,w-.110f,.025f,2,-1,0,1,verts,quads);
    if(v->feed_index==1u)snprintf(footer,sizeof(footer),"OPEN MATCH CENTRE");
    else if(v->feed_index==2u)snprintf(footer,sizeof(footer),"POSITION %s / TARGET %s",s->stat_value[0],s->stat_value[1]);
    else if(v->feed_index==3u)snprintf(footer,sizeof(footer),"WINDOW %s / %s COMPLETED DEALS",s->stat_value[0],s->stat_value[1]);
    else snprintf(footer,sizeof(footer),"SEASON %s / %s",s->stat_value[0],s->stat_value[1]);
  }
  ml_ui_text(ui,footer,x+.021f,y+.185f,w-.102f,.021f,0,-1,0,1,verts,quads);
  for(uint32_t i=content;i<ui->draw_count;i++)ui->draws[i].color[3]*=v->feed_opacity;
  for(uint32_t i=0;i<4u;i++) {
    const float xx=x+w-.069f+i*.013f;
    ml_ui_rect(ui,xx,y+.191f,.007f,.0124f,1,1,1,i==v->feed_index ? 1.f : .38f,-1,0,1,verts,quads);
    ui->draws[ui->draw_count-1u].round.radius=5.f;
  }
  if(v->feed_progress>0.f) {
    ml_ui_rect(ui,x+.021f,y+.214f,(w-.042f)*v->feed_progress,.003f,.07f,.77f,.90f,.8f,-1,0,1,verts,quads);
    ui->draws[ui->draw_count-1u].round.radius=0.f;
  }
}
static void ml_ui_feature(MasterLeagueRender *ui,const MlView *v,uint32_t item,
    uint32_t art,float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const MlViewRow *r=&v->rows[item];const int selected=v->selected==item && r->enabled;
  ml_ui_frame(ui,x,y,w,h,selected,verts,quads);
  ml_ui_art(ui,art,x,y,w,h,verts,quads);
  if(!v->section && item==1u){ml_ui_feed_summary(ui,v,x,y,w,verts,quads);return;}
  if(r->unread)ml_ui_unread(ui,x+w-.023f,y+.023f,verts,quads);
  ml_ui_text(ui,r->label,x+.021f,y+.021f,w-.04f,.0444f,0,-1,0,1,verts,quads);
  if(v->section==0u && item==0u && v->next.home[0]) {
    ml_ui_image(ui,gl.badge_tex,v->next.home_badge,x+w*.23f-.022f,y+.065f,.044f,.0782f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,v->next.away_badge,x+w*.77f-.022f,y+.065f,.044f,.0782f,verts,quads);
    ml_ui_text(ui,"VS",x+w*.47f,y+.105f,.04f,.030f,0,-1,0,1,verts,quads);
    ml_ui_center_text(ui,v->next.home,x+w*.015f,y+.145f,w*.43f,.036f,.025f,0,-1,verts,quads);
    ml_ui_center_text(ui,v->next.away,x+w*.555f,y+.145f,w*.43f,.036f,.025f,0,-1,verts,quads);
    char match[112];snprintf(match,sizeof(match),"%s  /  %.65s",v->next.day,v->next.competition);
    ml_ui_text(ui,match,x+.021f,y+.188f,w-.04f,.021f,0,-1,0,1,verts,quads);
  } else {
    ml_ui_text(ui,r->detail,x+.021f,y+.100f,w-.05f,.0278f,2,-1,0,1,verts,quads);
    char value[80];
    if(v->section==1u && item==0u) snprintf(value,sizeof(value),"%u REGISTERED PLAYERS",v->squad_size);
    else if(v->section==2u && item==0u) snprintf(value,sizeof(value),"TRANSFER BALANCE  %s",v->balance);
    else if(v->section==3u && item==0u) snprintf(value,sizeof(value),"YOUR POSITION  %u",v->rank);
    else snprintf(value,sizeof(value),"%s",r->value[0] ? r->value : "VIEW DETAILS");
    ml_ui_text(ui,value,x+.021f,y+.170f,w-.05f,.025f,2,-1,0,1,verts,quads);
  }
}
static void ml_ui_row(MasterLeagueRender *ui,const MlViewRow *row,float x,float y,float w,float h,
    int selected,int large,GLfloat *verts,int *quads) {
  ml_ui_frame(ui,x,y,w,h,selected && row->enabled,verts,quads);
  const int ink=selected && row->enabled ? -1 : row->enabled ? -2 : -3;
  if(selected && row->enabled)ml_ui_art(ui,0,x,y,w,h,verts,quads);
  else ml_ui_rect(ui,x,y,w,h,row->enabled ? .93f : .89f,row->enabled ? .96f : .91f,.98f,1,-1,0,1,verts,quads);
  if(row->unread)ml_ui_unread(ui,x+w-.020f,y+.010f,verts,quads);
  const float icon_h=fminf(h-.012f,.061f),icon_w=icon_h*screen_height/screen_width;
  const int has_icon=row->badge || row->portrait || row->league_logo || row->emblem;
  const float icon_span=has_icon ? icon_w+.010f+(row->badge && row->portrait ? icon_w+.008f : 0.f) : 0.f;
  if(row->emblem && !row->badge && !row->portrait)ml_ui_emblem(ui,row->emblem-1u,x+.010f,y+(h-icon_h)*.5f,icon_h,verts,quads);
  if(row->badge && !row->league_logo)ml_ui_image(ui,gl.badge_tex,row->badge,
      x+.010f+(row->portrait ? icon_w+.008f : 0.f),y+(h-icon_h)*.5f,icon_w,icon_h,verts,quads);
  if(row->portrait) {
    const GLuint tex=gameplan_portrait_texture(row->portrait);
    if(tex)ml_ui_image(ui,tex,0,x+.010f,y+(h-icon_h)*.5f,icon_w,icon_h,verts,quads);
  }
  if(row->league_logo) {
    const uint32_t index=row->league_logo-1u;
    prepare_league_logo_index(index);
    if(index<FL26_LEAGUE_CATALOG_COUNT && gl.league_logo_uploaded[index]) {
      const float aspect=gl.league_logo_aspect[index]>0.f ? gl.league_logo_aspect[index] : 1.f;
      const float iw=icon_w*fminf(1.f,aspect),ih=icon_h*fminf(1.f,1.f/aspect);
      ml_ui_image(ui,gl.league_logo_tex[index],0,x+.010f+(icon_w-iw)*.5f,y+(h-ih)*.5f,iw,ih,verts,quads);
    } else if(row->badge)ml_ui_image(ui,gl.badge_tex,row->badge,x+.010f,y+(h-icon_h)*.5f,icon_w,icon_h,verts,quads);
  }
  /* The unread dot occupies the upper corner, not the fee's centre line. */
  const float right_inset=.015f;
  const float tx=x+.015f+icon_span,available=w-(tx-x)-right_inset;
  if(row->rating) {
    ml_ui_text(ui,row->label,tx,y+.010f,available-.053f,.0306f,0,ink,0,1,verts,quads);
    const float red=row->role==0u ? .90f : row->role<4u ? .06f : row->role<9u ? .04f : .85f;
    const float green=row->role==0u ? .47f : row->role<4u ? .48f : row->role<9u ? .55f : .10f;
    const float blue=row->role<4u && row->role ? .90f : .21f;
    ml_ui_rect(ui,tx,y+h-.038f,.039f,.029f,red,green,blue,1,-1,0,1,verts,quads);
    ml_ui_center_text(ui,row->detail,tx,y+h-.038f,.039f,.029f,.022f,0,-1,verts,quads);
    if(row->value[0])ml_ui_text(ui,row->value,tx+.048f,y+h-.035f,available-.108f,.024f,2,ink,0,1,verts,quads);
    char rating[8];snprintf(rating,sizeof(rating),"%u",row->rating);
    /* High ratings move from blue/green through amber to red. */
    ml_ui_center_text(ui,rating,x+w-.064f,y,.057f,h,.049f,0,-1,verts,quads);
    MlDraw *d=&ui->draws[ui->draw_count-1u];const float t=fminf(1.f,fmaxf(0.f,((float)row->rating-60.f)/39.f));
    d->color[0]=t<.4f ? .05f : .05f+.89f*(t-.4f)/.6f;
    d->color[1]=t<.4f ? .40f+.25f*t/.4f : .65f-.50f*(t-.4f)/.6f;
    d->color[2]=t<.4f ? .87f-.47f*t/.4f : .40f-.25f*(t-.4f)/.6f;
    return;
  }
  if(row->adjustable==2u) {
    ml_ui_text(ui,row->label,tx,y+.004f,available,.0222f,0,ink,0,1,verts,quads);
    const float vy=y+.031f,vh=h-.036f,ih=.034f,iw=ih*screen_height/screen_width;
    ml_ui_rect(ui,x+.007f,vy,w-.014f,vh,.96f,.98f,1.f,1,-1,0,1,verts,quads);
    ml_ui_icon(ui,0u,x+.014f,vy+(vh-ih)*.5f,ih,verts,quads);
    ml_ui_icon(ui,1u,x+w-.014f-iw,vy+(vh-ih)*.5f,ih,verts,quads);
    ml_ui_center_text(ui,row->value,x+.043f,vy,w-.086f,vh,.0333f,0,-2,verts,quads);return;
  }
  if(row->adjustable) {
    const float vw=fminf(w*.46f,.215f),vx=x+w-vw-.012f;
    ml_ui_text(ui,row->label,tx,y+(h-.0264f)*.5f,vx-tx-.010f,.0264f,0,ink,0,1,verts,quads);
    /* Pale value well keeps generated navy arrows readable on selected art. */
    ml_ui_rect(ui,vx,y+.005f,vw,h-.010f,.96f,.98f,1.f,1,-1,0,1,verts,quads);
    ml_ui_icon(ui,0u,vx+.002f,y+(h-.044f)*.5f,.044f,verts,quads);
    ml_ui_icon(ui,1u,vx+vw-.027f,y+(h-.044f)*.5f,.044f,verts,quads);
    ml_ui_center_text(ui,row->value,vx+.025f,y,vw-.050f,h,.026f,0,-2,verts,quads);return;
  }
  const float size=large==2 ? .0417f : large ? .0556f : h<.07f ? (row->detail[0] ? .0264f : .028f) : .031f;
  const float detail_size=large ? .031f : h<.07f ? .024f : .0264f;
  const float value_width=row->value[0] ? fminf(available*.44f,.16f) : 0.f;
  const float text_gap=large ? .021f : .010f;
  const float label_y=row->detail[0] ? y+(h-size-detail_size-text_gap)*.5f : y+(h-size)*.5f;
  ml_ui_text(ui,row->label,tx,label_y,available-value_width-(value_width ? .018f : 0.f),size,0,ink,0,1,verts,quads);
  if(row->detail[0])ml_ui_text(ui,row->detail,tx,label_y+size+text_gap,available,detail_size,2,ink,0,1,verts,quads);
  if(row->value[0]) {
    const float text_width=fminf(value_width,measure_efootball_line_mode(row->value,(int)strlen(row->value),
      .028f*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width);
    ml_ui_text(ui,row->value,x+w-right_inset-text_width,y+(h-.028f)*.5f,text_width+.001f,.028f,0,ink,0,1,verts,quads);
  }
}
static void ml_ui_pills(MasterLeagueRender *ui,uint32_t selected,float y,GLfloat *verts,int *quads) {
  /* Constant total width: active pill is longer, gaps stay exactly 10px. */
  const float dot=10.f/screen_width,active=32.f/screen_width,gap=10.f/screen_width;
  float x=.5f-(active+3.f*dot+3.f*gap)*.5f;
  for(uint32_t i=0;i<4u;i++) {
    const float w=i==selected ? active : dot;
    ml_ui_rect(ui,x,y,w,10.f/screen_height,.02f,i==selected ? .39f : .62f,i==selected ? .68f : .73f,1,-1,0,1,verts,quads);
    ui->draws[ui->draw_count-1u].round.radius=5.f;x+=w+gap;
  }
}
static void ml_ui_calendar(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;
  ml_ui_panel(ui,v->calendar_month,ML_HEADER_CALENDAR,.04f,.205f,.92f,.684f,0,verts,quads);
  static const char *days[]={"MON","TUE","WED","THU","FRI","SAT","SUN"};
  const float w=.122f,gap=.006f;
  uint32_t last=0u;
  for(uint32_t i=0;i<v->calendar_count;i++)if(v->calendar[i].day)last=i;
  const uint32_t weeks=last/7u+1u;
  const float row_gap=.008f,rh=(.490f-(weeks-1u)*row_gap)/weeks;
  for(uint32_t i=0;i<7u;i++)ml_ui_center_text(ui,days[i],.055f+i*(w+gap),.287f,w,.031f,.025f,0,-3,verts,quads);
  for(uint32_t i=0;i<v->calendar_count;i++) {
    const MlCalendarCell *c=&v->calendar[i];const float x=.055f+(i%7u)*(w+gap),y=.327f+(i/7u)*(rh+row_gap);
    if(!c->day)continue;
    if(c->selected)ml_ui_frame(ui,x,y,w,rh,1,verts,quads);
    ml_ui_rect(ui,x,y,w,rh,c->kind==2u ? .99f : .93f,c->kind==2u ? .92f : .96f,c->kind==2u ? .92f : .99f,1,-1,0,1,verts,quads);
    char date[8];snprintf(date,sizeof(date),"%u",c->day);
    ml_ui_text(ui,date,x+.009f,y+.005f,.032f,.0278f,0,-2,0,1,verts,quads);
    if(c->transfer)ml_ui_icon(ui,2u,x+w-.040f,y+.002f,.052f,verts,quads);
    if(c->current && !c->transfer) {
      ml_ui_rect(ui,x+.047f,y+.012f,.055f,.022f,.02f,.37f,.67f,1,-1,0,1,verts,quads);
      ml_ui_center_text(ui,"TODAY",x+.047f,y+.010f,.055f,.026f,.019f,0,-1,verts,quads);
    } else if(c->badge)ml_ui_image(ui,gl.badge_tex,c->badge,x+w-.033f,y+.005f,.0248f,.044f,verts,quads);
    ml_ui_text(ui,c->detail,x+.009f,y+rh-.026f,w-.016f,.0236f,2,-2,0,1,verts,quads);
    if(v->page==ML_PAGE_ADVANCE && c->selected)
      ml_ui_rect(ui,x,y,w*(.12f+.88f*v->advance_fraction),.004f,.07f,.77f,.70f,1,-1,0,1,verts,quads);
  }
  ml_ui_text(ui,v->calendar_detail,.061f,.835f,.873f,.0292f,2,-2,0,1,verts,quads);
}
static float ml_ui_paragraph(MasterLeagueRender *ui,const char *text,float x,float y,float w,
    float size,uint32_t lines,int ink,GLfloat *verts,int *quads);
static void ml_ui_primary(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;
  static MlDrawerView retained;
  static uint32_t serial;
  static uint64_t started;
  static float initial,progress;
  if(serial!=v->drawer.serial) {serial=v->drawer.serial;started=armGetSystemTick();initial=progress;}
  if(v->drawer.open)retained=v->drawer;
  const float raw=(float)armTicksToNs(armGetSystemTick()-started)/200000000.f;
  const float t=fminf(1.f,raw),e=t*t*(3.f-2.f*t);
  progress=initial+((v->drawer.open ? 1.f : 0.f)-initial)*e;
  const float shift=retained.modal ? 0.f : progress;
  const float x=.13f-.08f*shift,w=.74f-.175f*shift;
  const int setting=v->page==ML_PAGE_SETTINGS;
  ml_ui_panel(ui,v->left_title,ml_ui_page_icon(v->page),x,.205f,w,.630f,0,verts,quads);
  const int actions=v->page==ML_PAGE_LANDING || v->page==ML_PAGE_MANAGER || v->page==ML_PAGE_SQUAD ||
      v->page==ML_PAGE_NEXT || v->page==ML_PAGE_SLOTS || v->page==ML_PAGE_MY_TEAM || v->page==ML_PAGE_MANAGER_OFFICE || v->page==ML_PAGE_COMPETITIONS;
  const float gap=setting ? .006f : .016f;
  const float body_top=.280f,body_bottom=v->total>5u && !setting ? .799f : .835f;
  const float usable=body_bottom-body_top-.036f;
  const float fitted=v->count ? (usable-(v->count-1u)*gap)/v->count : 0.f;
  /* Action groups with one/two destinations are centred. Three/four cards
   * fill the panel. Short data lists keep bounded heights, even on a last page. */
  const float rh=setting ? .063f : actions ? fminf(.215f,fitted) :
      v->total>5u ? .086f : fminf(.125f,fitted);
  const float group=v->count ? v->count*rh+(v->count-1u)*gap : 0.f;
  const float row_y=setting || !actions || v->total>5u ? .297f : body_top+(body_bottom-body_top-group)*.5f;
  for(uint32_t i=0;i<v->count;i++) {
    const int selected=!v->drawer.open && !v->action_selected && v->first+i==v->selected;
    ml_ui_row(ui,&v->rows[i],x+.017f,row_y+i*(rh+gap),w-.034f,rh,selected,
        actions ? (v->count<=2u ? 1 : 2) : 0,verts,quads);
  }
  if(v->empty[0]) {
    ml_ui_icon(ui,3u,x+w*.5f-.069f,.385f,.245f,verts,quads);
    ml_ui_center_text(ui,v->empty,x+.02f,.655f,w-.04f,.060f,.036f,2,-3,verts,quads);
  }else if(!v->count)for(uint32_t i=0;i<8u;i++)ml_ui_text(ui,v->info[i],x+.028f,.306f+i*.058f,w-.056f,.0292f,2,-2,0,1,verts,quads);
  if(v->total>5u && !setting) {
    char count[40];snprintf(count,sizeof(count),"%u-%u / %u",v->total ? v->first+1u : 0u,v->first+v->count,v->total);
    ml_ui_text(ui,count,x+.019f,.805f,w-.04f,.0236f,2,-3,0,1,verts,quads);
  }
  for(uint32_t i=0;i<v->action_count;i++) {
    const float bw=.25f,bx=x+w*.5f-(v->action_count*.267f-.017f)*.5f+i*.267f;
    const int selected=!v->drawer.open && v->action_selected && v->action_focus==i;
    ml_ui_button(ui,bx,.851f,bw,.054f,selected,v->action_enabled[i],verts,quads);
    ml_ui_center_text(ui,v->action[i],bx,.851f,bw,.054f,.031f,0,v->action_enabled[i] ? -1 : -3,verts,quads);
  }
  if(progress>.001f) {
    const MlDrawerView *d=&retained;const float dx=.633f+(1.f-progress)*.40f,dw=.317f;
    if(d->modal) {
      const uint32_t start=ui->draw_count;
      ml_ui_rect(ui,0,0,1,1,.01f,.035f,.10f,.64f*progress,-1,0,1,verts,quads);
      ui->draws[ui->draw_count-1u].round.radius=0.f;
      const float px=.20f,pw=.60f,pad=.027f;
      const float body_h=d->modal==2 ? ml_ui_paragraph(NULL,d->body,0,0,pw-.060f,.0278f,8u,-3,NULL,NULL) : 0.f;
      const float error_h=ml_ui_paragraph(NULL,v->status,0,0,pw-.060f,.025f,4u,-2,NULL,NULL);
      const float identity_h=d->modal==2 ? fmaxf(d->badge ? .096f : 0.f,
        (d->subtitle[0] ? .037f : 0.f)+(d->detail[0] ? .009f+.0264f : 0.f)) : .0389f;
      float cursor=.075f+pad;
      const float identity_y=cursor;cursor+=identity_h;
      float value_y=0.f,body_y=0.f,error_y=0.f;
      if(d->modal==2 && d->value[0]){cursor+=.018f;value_y=cursor;cursor+=.0292f;}
      if(body_h>0.f){cursor+=.020f;body_y=cursor;cursor+=body_h;}
      if(error_h>0.f){cursor+=.018f;error_y=cursor;cursor+=error_h;}
      cursor+=.026f;
      const float rows_y=cursor,rh=d->modal==2 ? .080f : .096f,gap=.017f;
      if(d->count)cursor+=d->count*rh+(d->count-1u)*gap;
      else if(d->modal==2)cursor+=.064f;
      float confirm_y=0.f;
      if(d->modal!=2){cursor+=.023f;confirm_y=cursor;cursor+=.065f;}
      const float ph=cursor+pad,py=(1.f-ph)*.5f+(1.f-progress)*.025f;
      ml_ui_panel(ui,d->title,ml_ui_page_icon(v->page),px,py,pw,ph,0,verts,quads);
      const float tx=px+(d->modal==2 && d->badge ? .10f : .030f);
      if(d->modal==2 && d->badge)ml_ui_image(ui,gl.badge_tex,d->badge,px+.03f,py+identity_y,.054f,.096f,verts,quads);
      ml_ui_text(ui,d->subtitle,tx,py+identity_y,pw-(tx-px)-.03f,d->modal==2 ? .037f : .0389f,0,-2,0,1,verts,quads);
      if(d->modal==2) {
        ml_ui_text(ui,d->detail,tx,py+identity_y+.046f,pw-(tx-px)-.03f,.0264f,2,-3,0,1,verts,quads);
        if(value_y)ml_ui_text(ui,d->value,px+.03f,py+value_y,pw-.06f,.0292f,0,-2,0,1,verts,quads);
        if(body_h)ml_ui_paragraph(ui,d->body,px+.03f,py+body_y,pw-.06f,.0278f,8u,-3,verts,quads);
      }
      if(error_h)ml_ui_paragraph(ui,v->status,px+.03f,py+error_y,pw-.06f,.025f,4u,-2,verts,quads);
      for(uint32_t i=0;i<d->count;i++)ml_ui_row(ui,&d->rows[i],px+pad,py+rows_y+i*(rh+gap),pw-2.f*pad,rh,
          i==d->selected,0,verts,quads);
      if(d->modal==2 && !d->count) {
        ml_ui_icon(ui,2u,px+.030f,py+rows_y,.064f,verts,quads);
        ml_ui_text(ui,"NO ACTION REQUIRED",px+.082f,py+rows_y+.018f,pw-.112f,.0278f,0,-3,0,1,verts,quads);
      }else if(d->modal!=2) {
        ml_ui_button(ui,px+.16f,py+confirm_y,pw-.32f,.065f,d->confirm_selected,1,verts,quads);
        ml_ui_center_text(ui,d->confirm_label,px+.16f,py+confirm_y,pw-.32f,.065f,.0333f,0,-1,verts,quads);
      }
      for(uint32_t i=start;i<ui->draw_count;i++)ui->draws[i].layer=2;
      return;
    }
    ml_ui_panel(ui,d->title,ml_ui_page_icon(v->page),dx,.205f,dw,.630f,0,verts,quads);
    if(d->subtitle[0])ml_ui_text(ui,d->subtitle,dx+.015f,.297f,dw-.03f,.0306f,0,-2,0,1,verts,quads);
    if(d->detail[0])ml_ui_text(ui,d->detail,dx+.015f,.336f,dw-.03f,.025f,2,-3,0,1,verts,quads);
    if(d->value[0])ml_ui_text(ui,d->value,dx+.015f,.369f,dw-.03f,.025f,2,-3,0,1,verts,quads);
    if(d->body[0]) {
      const char *p=d->body;float yy=.310f;
      while(*p && yy<.70f) {
        char line[96];uint32_t n=0u,last=0u;
        while(p[n] && n<80u) {
          line[n]=p[n];line[n+1u]=0;
          if(measure_efootball_line_mode(line,(int)n+1,.0292f*screen_height,EFOOTBALL_FONT_REGULAR,0)>(dw-.038f)*screen_width)break;
          if(p[n]==' ')last=n;
          n++;
        }
        if(p[n] && last)n=last;
        if(!n)break;
        memcpy(line,p,n);line[n]=0;ml_ui_text(ui,line,dx+.019f,yy,dw-.038f,.0292f,2,-2,0,1,verts,quads);
        p+=n;while(*p==' ')p++;yy+=.042f;
      }
    }
    for(uint32_t i=0;i<d->count;i++) {
      const float rh=d->confirm ? (d->count>3u ? .055f : .085f) : d->total>5u ? .085f :
        fminf(.125f,(.498f-(d->count-1u)*.013f)/d->count);
      const float top=d->confirm ? .408f : .297f;
      const float yy=top+i*(rh+.013f);
      ml_ui_row(ui,&d->rows[i],dx+.012f,yy,dw-.029f,rh,d->first+i==d->selected,0,verts,quads);
    }
    if(d->confirm==1) {
      ml_ui_button(ui,dx+.027f,.759f,dw-.054f,.056f,d->confirm_selected,1,verts,quads);
      ml_ui_center_text(ui,d->confirm_label[0] ? d->confirm_label : "CONFIRM",dx+.027f,.759f,dw-.054f,.056f,.030f,0,-1,verts,quads);
    } else if(!d->confirm && d->total) {
      char count[40];snprintf(count,sizeof(count),"%u-%u / %u",d->total ? d->first+1u : 0u,d->first+d->count,d->total);
      ml_ui_text(ui,count,dx+.018f,.805f,dw-.036f,.0236f,2,-3,0,1,verts,quads);
      if(d->total>5u) {
        ml_ui_rect(ui,dx+dw-.009f,.289f,.003f,.454f,.83f,.88f,.94f,1,-1,0,1,verts,quads);
        const float thumb=.454f*5.f/d->total,top=.289f+(.454f-thumb)*d->first/(d->total-5u);
        ml_ui_rect(ui,dx+dw-.009f,top,.003f,thumb,.03f,.38f,.69f,1,-1,0,1,verts,quads);
      }
    }
  }
}
static void ml_ui_table(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;
  ml_ui_panel(ui,v->page==ML_PAGE_QUALIFIERS ? v->left_title : "LEAGUE STANDINGS",ML_HEADER_RANKING,.04f,.205f,.92f,.675f,0,verts,quads);
  const char *columns[]={"P","W","D","L","GF","GA","GD","PTS"};
  const float xs[]={.532f,.585f,.638f,.691f,.744f,.797f,.850f,.907f};
  ml_ui_text(ui,"POS",.062f,.303f,.041f,.025f,0,-3,0,1,verts,quads);
  ml_ui_text(ui,"CLUB",.152f,.303f,.34f,.025f,0,-3,0,1,verts,quads);
  for(uint32_t j=0;j<8u;j++)ml_ui_center_text(ui,columns[j],xs[j],.299f,.041f,.034f,.025f,0,-3,verts,quads);
  for(uint32_t i=0;i<v->table_count;i++) {
    const MlTableRow *r=&v->table[i];const float y=.342f+i*.060f;
    const int selected=v->first+i==v->selected;
    ml_ui_rect(ui,.055f,y,.89f,.057f,selected ? .03f : r->own ? .83f : i%2u ? 1.f : .94f,
      selected ? .28f : r->own ? .94f : i%2u ? 1.f : .97f,selected ? .60f : 1.f,1,-1,0,1,verts,quads);
    const int ink=selected ? -1 : -2;char number[20];snprintf(number,sizeof(number),"%u",r->rank);
    ml_ui_text(ui,number,.064f,y+.013f,.033f,.0306f,0,ink,0,1,verts,quads);
    ml_ui_image(ui,gl.badge_tex,r->badge,.108f,y+.003f,.0287f,.051f,verts,quads);
    ml_ui_text(ui,r->name,.152f,y+.012f,.361f,.0333f,0,ink,0,1,verts,quads);
    const int values[]={(int)r->stats.played,(int)r->stats.wins,(int)r->stats.draws,(int)r->stats.losses,
      (int)r->stats.goals_for,(int)r->stats.goals_against,(int)r->stats.goals_for-(int)r->stats.goals_against,(int)r->stats.points};
    for(uint32_t j=0;j<8u;j++) {
      snprintf(number,sizeof(number),j==6u ? "%+d" : "%d",values[j]);
      ml_ui_center_text(ui,number,xs[j],y,.041f,.057f,.0306f,j==7u ? 0 : 2,ink,verts,quads);
    }
  }
  char pages[48];snprintf(pages,sizeof(pages),"%u-%u / %u CLUBS",v->first+1u,v->first+v->table_count,v->total);
  ml_ui_text(ui,pages,.062f,.839f,.50f,.025f,2,-3,0,1,verts,quads);
}
static void ml_ui_bracket(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;
  ml_ui_panel(ui,"KNOCKOUT BRACKET",ML_HEADER_TROPHY,.04f,.205f,.92f,.675f,0,verts,quads);
  for(uint32_t col=0;col<3u;col++)ml_ui_center_text(ui,v->bracket_titles[col],.061f+col*.305f,.298f,.265f,.044f,.028f,0,-3,verts,quads);
  for(uint32_t i=0;i<v->bracket_count;i++) {
    const MlBracketMatch *m=&v->bracket[i];const float x=.061f+m->round*.305f;
    const float y=.357f+(m->round==0u ? m->index*.114f : m->round==1u ? .057f+m->index*.228f : .171f);
    if(m->round && m->index<(4u>>m->round)) {
      const float delta=m->round==1u ? .057f : .114f;
      ml_ui_rect(ui,x-.020f,y+.046f-delta,.002f,delta*2.f,.70f,.78f,.87f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,x-.020f,y+.045f,.020f,.003f,.70f,.78f,.87f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,x-.040f,y+.045f-delta,.020f,.003f,.70f,.78f,.87f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,x-.040f,y+.045f+delta,.020f,.003f,.70f,.78f,.87f,1,-1,0,1,verts,quads);
    }
    ml_ui_rect(ui,x,y,.265f,.092f,m->own ? .85f : .94f,.96f,.99f,1,-1,0,1,verts,quads);
    for(uint32_t side=0;side<2u;side++) {
      const float yy=y+.005f+side*.044f;const uint32_t badge=side ? m->away_badge : m->home_badge;
      if(badge)ml_ui_image(ui,gl.badge_tex,badge,x+.009f,yy,.0203f,.036f,verts,quads);
      ml_ui_text(ui,side ? m->away : m->home,x+.037f,yy+.005f,.192f,.025f,0,-2,0,1,verts,quads);
      char score[8];snprintf(score,sizeof(score),"%u",side ? m->ag : m->hg);
      ml_ui_text(ui,m->complete ? score : "-",x+.235f,yy+.005f,.025f,.0264f,0,-2,0,1,verts,quads);
    }
  }
  char pages[80];snprintf(pages,sizeof(pages),"SECTION %u / %u    UP / DOWN: BRACKET SECTION",v->bracket_page+1u,v->bracket_pages);
  ml_ui_text(ui,pages,.062f,.839f,.86f,.025f,2,-3,0,1,verts,quads);
}
static void ml_ui_toast_card(MasterLeagueRender *ui,const char *text,float slide,GLfloat *verts,int *quads) {
  const float x=.66f+slide*.35f;
  const uint32_t first=ui->draw_count;
  ml_ui_rect(ui,x,.181f,.31f,.072f,.025f,.20f,.43f,1,-1,0,1,verts,quads);
  ml_ui_rect(ui,x,.181f,.004f,.072f,.07f,.77f,.70f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,text,x+.016f,.205f,.278f,.0278f,0,-1,0,1,verts,quads);
  for(uint32_t i=first;i<ui->draw_count;i++)ui->draws[i].layer=1;
}
static void ml_ui_toast(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;static uint32_t serial;static uint64_t began;
  if(serial!=v->toast_serial){serial=v->toast_serial;began=armGetSystemTick();}
  const float ms=(float)armTicksToNs(armGetSystemTick()-began)/1000000.f;
  if(!v->toast[0] || ms>=3000.f || (v->drawer.open && v->drawer.modal) || v->modal.open)return;
  const float enter=fminf(1.f,ms/180.f),leave=fmaxf(0.f,(ms-2750.f)/250.f);
  ml_ui_toast_card(ui,v->toast,(1.f-enter)*(1.f-enter)+leave*leave,verts,quads);
}
static float ml_ui_paragraph(MasterLeagueRender *ui,const char *text,float x,float y,float w,
    float size,uint32_t lines,int ink,GLfloat *verts,int *quads) {
  const char *p=text;uint32_t used=0u;
  for(uint32_t line=0u;*p && line<lines;line++) {
    char part[112]={0};uint32_t n=0u,space=0u;
    while(p[n] && p[n]!='\n' && n<110u) {
      part[n]=p[n];part[n+1u]=0;
      if(measure_efootball_line_mode(part,(int)n+1,size*screen_height,EFOOTBALL_FONT_REGULAR,0)>w*screen_width)break;
      if(p[n]==' ')space=n;
      n++;
    }
    if(p[n] && p[n]!='\n' && space)n=space;
    if(!n)break;
    memcpy(part,p,n);part[n]=0;
    if(ui)ml_ui_text(ui,part,x,y+line*(size+.014f),w,size,2,ink,0,1,verts,quads);
    used++;
    p+=n;while(*p==' ' || *p=='\n')p++;
  }
  return used ? used*(size+.014f)-.014f : 0.f;
}
static void ml_ui_confirmation(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const MlModalView *m=&ui->view.modal;if(!m->open)return;
  const uint32_t first=ui->draw_count;
  ml_ui_rect(ui,0,0,1,1,.01f,.035f,.10f,.72f,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0.f;
  const float body_h=ml_ui_paragraph(NULL,m->body,0,0,.49f,.0333f,8u,-2,NULL,NULL);
  const float error_h=ml_ui_paragraph(NULL,m->error,0,0,.49f,.025f,4u,-2,NULL,NULL);
  const float actions_y=.105f+body_h+(error_h ? .018f+error_h : 0.f)+.030f;
  const float ph=actions_y+.065f+.030f,py=(1.f-ph)*.5f;
  ml_ui_panel(ui,m->title,ml_ui_page_icon(ui->view.page),.225f,py,.55f,ph,0,verts,quads);
  ml_ui_paragraph(ui,m->body,.255f,py+.105f,.49f,.0333f,8u,-2,verts,quads);
  if(error_h)ml_ui_paragraph(ui,m->error,.255f,py+.123f+body_h,.49f,.025f,4u,-2,verts,quads);
  for(uint32_t i=0;i<2u;i++) {
    const float x=.255f+i*.251f;
    ml_ui_button(ui,x,py+actions_y,.239f,.065f,m->selected==i,1,verts,quads);
    ml_ui_center_text(ui,i ? "CANCEL" : m->accept,x,py+actions_y,.239f,.065f,.032f,0,-1,verts,quads);
  }
  for(uint32_t i=first;i<ui->draw_count;i++)ui->draws[i].layer=3;
}
static void ml_ui_story(MasterLeagueRender *ui,float slide,GLfloat *verts,int *quads) {
  const MlView *v=&ui->view;const MlStoryView *s=&v->story;
  const float x=.05f+slide,hx=x+.014f,hw=.40f,rx=x+.438f,rw=.446f;
  static const char *kickers[]={"THE MANAGER","MATCH CENTRE","SEASON JOURNAL","TRANSFER JOURNAL"};
  ml_ui_panel(ui,kickers[v->feed_index],ML_HEADER_NEWS,x,.205f,.90f,.630f,0,verts,quads);
  ml_ui_art(ui,v->feed_index==1u ? 1u : v->feed_index==2u ? 0u : 3u,hx,.297f,hw,.518f,verts,quads);
  ml_ui_text(ui,"CLUB STORIES",hx+.024f,.321f,hw-.048f,.025f,0,-1,0,1,verts,quads);
  char number[32];snprintf(number,sizeof(number),"%02u / %02u",v->feed_index+1u,v->feed_count);
  ml_ui_text(ui,number,hx+.024f,.758f,hw-.048f,.036f,1,-1,0,1,verts,quads);
  if(v->feed_index==1u && s->has_result) {
    ml_ui_image(ui,gl.badge_tex,s->home_badge,hx+.050f,.405f,.080f,.1422f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,s->away_badge,hx+hw-.130f,.405f,.080f,.1422f,verts,quads);
    char score[24];snprintf(score,sizeof(score),"%u - %u",s->home_goals,s->away_goals);
    ml_ui_center_text(ui,score,hx+.130f,.427f,hw-.260f,.09f,.0667f,0,-1,verts,quads);
    ml_ui_center_text(ui,s->home,hx+.012f,.575f,.176f,.080f,.0306f,0,-1,verts,quads);
    ml_ui_center_text(ui,s->away,hx+.212f,.575f,.176f,.080f,.0306f,0,-1,verts,quads);
    char result[64];snprintf(result,sizeof(result),"FULL TIME / %s",s->result);
    ml_ui_center_text(ui,result,hx+.02f,.662f,hw-.04f,.036f,.0278f,0,-1,verts,quads);
    ml_ui_center_text(ui,s->competition,hx+.02f,.709f,hw-.04f,.030f,.0236f,0,-1,verts,quads);
  }else {
    if(s->club_badge)ml_ui_image(ui,gl.badge_tex,s->club_badge,hx+.143f,.402f,.114f,.203f,verts,quads);
    if(v->feed_index==3u)ml_ui_icon(ui,2u,hx+.273f,.536f,.097f,verts,quads);
    ml_ui_center_text(ui,v->club_name,hx+.016f,.644f,hw-.032f,.073f,.0333f,0,-1,verts,quads);
  }
  ml_ui_emblem(ui,v->feed_index==0u ? 2u : v->feed_index==2u ? 0u : 3u,rx+rw-.051f,.305f,.075f,verts,quads);
  ml_ui_text(ui,s->headline,rx,.316f,rw-.065f,.043f,0,-2,0,1,verts,quads);
  float summary_x=rx;
  if(v->feed_index==0u && s->nation_badge) {
    ml_ui_image(ui,gl.badge_tex,s->nation_badge,rx,.375f,.0253f,.045f,verts,quads);summary_x+=.037f;
  }
  ml_ui_text(ui,s->summary,summary_x,.380f,rw-(summary_x-rx),.0292f,2,-3,0,1,verts,quads);
  if(v->feed_index==0u || v->feed_index==2u) {
    for(uint32_t i=0;i<3u;i++) {
      const float yy=.421f+i*.119f;
      ml_ui_rect(ui,rx,yy,rw,.103f,.93f,.96f,.99f,1,-1,0,1,verts,quads);
      ml_ui_text(ui,s->stat_label[i],rx+.016f,yy+.014f,rw-.032f,.024f,0,-3,0,1,verts,quads);
      ml_ui_text(ui,s->stat_value[i],rx+.016f,yy+.049f,rw-.032f,.039f,0,-2,0,1,verts,quads);
    }
  }else if(s->history_count) {
    if(v->feed_index==3u) {
      char caption[80];snprintf(caption,sizeof(caption),"WINDOW %s / %s RECENT COMPLETIONS",s->stat_value[0],s->stat_value[1]);
      ml_ui_text(ui,caption,rx,.783f,rw,.0236f,0,-3,0,1,verts,quads);
    }
    for(uint32_t i=0;i<s->history_count;i++)ml_ui_row(ui,&s->history[i],rx,.421f+i*.113f,rw,.100f,0,0,verts,quads);
  }else {
    ml_ui_icon(ui,3u,rx+rw*.5f-.0506f,.493f,.180f,verts,quads);
    ml_ui_center_text(ui,v->feed_index==1u ? "No Matches Played Yet" : "No Transfer Activity Yet",rx,.713f,rw,.060f,.032f,2,-3,verts,quads);
  }
  ml_ui_pills(ui,v->feed_index,.872f,verts,quads);
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
  ml_ui_text(ui,v->title,tx,.049f,v->annual_budget[0] ? .49f : .80f,.0472f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,v->caption[0] ? v->caption : "YOUR CLUB. YOUR CAREER.",tx,.114f,v->annual_budget[0] ? .52f : .80f,.0278f,2,-1,0,1,verts,quads);
  if(v->annual_budget[0]) {
    ml_ui_text(ui,"ANNUAL BUDGET",.667f,.057f,.13f,.0222f,2,-1,0,1,verts,quads);
    ml_ui_text(ui,v->annual_budget,.667f,.098f,.14f,.0306f,0,-1,0,1,verts,quads);
    ml_ui_text(ui,"TRANSFER BUDGET",.817f,.057f,.145f,.0222f,2,-1,0,1,verts,quads);
    ml_ui_text(ui,v->transfer_budget,.817f,.098f,.145f,.0306f,0,-1,0,1,verts,quads);
  }

  if (v->page==ML_PAGE_HUB) {
    static const uint32_t icons[4][5]={
      {ML_HEADER_MATCH,ML_HEADER_NEWS,ML_HEADER_CALENDAR,ML_HEADER_RANKING,ML_HEADER_SAVE},
      {ML_HEADER_SQUAD,ML_HEADER_CONTRACT,ML_HEADER_TRANSFER,ML_HEADER_SQUAD,ML_HEADER_NEWS},
      {ML_HEADER_TRANSFER,ML_HEADER_CONTRACT,ML_HEADER_FINANCE,ML_HEADER_MANAGER,ML_HEADER_SETTINGS},
      {ML_HEADER_RANKING,ML_HEADER_STATISTICS,ML_HEADER_TROPHY,ML_HEADER_RANKING,ML_HEADER_CALENDAR}
    };
    static const char *tabs[]={"HOME","SQUAD","CLUB OFFICE","COMPETITIONS"};
    for (uint32_t i=0;i<4u;i++) {
      const float x=.10f+i*.205f;
      const int selected=i==v->section;
      if(selected) ml_ui_frame(ui,x,.199f,.185f,.048f,1,verts,quads);
      ml_ui_rect(ui,x,.199f,.185f,.048f,selected ? .01f : 1.f,selected ? .36f : 1.f,selected ? .66f : 1.f,1,-1,0,1,verts,quads);
      ml_ui_text(ui,tabs[i],x+.018f,.211f,.159f,.025f,0,selected ? -1 : -2,0,1,verts,quads);
      if(i==2u && v->transfer_unread)ml_ui_unread(ui,x+.165f,.211f,verts,quads);
    }
    ui->shoulders=1;ui->shoulder_y=.222f;
    ml_ui_rect(ui,.049f,.204f,.034f,.038f,.03f,.18f,.45f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,.917f,.204f,.034f,.038f,.03f,.18f,.45f,1,-1,0,1,verts,quads);
    ml_ui_feature(ui,v,0,v->section==1u ? 2u : 0u,.04f+slide,.280f,.446f,.219f,verts,quads);
    ml_ui_feature(ui,v,1,v->section==2u ? 3u : 1u,.514f+slide,.280f,.446f,.219f,verts,quads);
    for(uint32_t item=2;item<=4u;item+=2u) {
      const float x=(item==2u ? .04f : .680f)+slide;
      const MlViewRow *r=&v->rows[item];
      ml_ui_panel(ui,r->label,icons[v->section][item],x,.535f,.280f,.298f,v->selected==item && r->enabled,verts,quads);
      if(r->unread)ml_ui_unread(ui,x+.259f,.557f,verts,quads);
      if(!v->section && item==2u) {
        ml_ui_minirows(ui,v->fixtures,v->fixture_count,x+.009f,.626f,.262f,0,verts,quads);
      } else if(!v->section && item==4u) {
        ml_ui_text(ui,v->club_name,x+.017f,.631f,.249f,.0278f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,v->season_summary,x+.017f,.667f,.249f,.025f,0,-3,0,1,verts,quads);
        ml_ui_text(ui,v->balance,x+.017f,.717f,.249f,.037f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,"CHOOSE SAVE SLOT",x+.017f,.787f,.249f,.025f,0,-3,0,1,verts,quads);
      } else {
        ml_ui_art(ui,item==2u ? 2u : 3u,x+.009f,.626f,.262f,.104f,verts,quads);
        ml_ui_text(ui,r->enabled ? "OPEN" : "UNAVAILABLE",x+.025f,.642f,.22f,.0347f,0,-1,0,1,verts,quads);
        ml_ui_text(ui,r->detail,x+.017f,.751f,.247f,.025f,0,-2,0,1,verts,quads);
        ml_ui_text(ui,r->enabled ? "VIEW DETAILS" : "NOT IN THIS LEAGUE",x+.017f,.792f,.247f,.0236f,0,-3,0,1,verts,quads);
      }
    }
    const float cx=.338f+slide;
    ml_ui_panel(ui,v->rows[3].label,icons[v->section][3],cx,.535f,.324f,.298f,v->selected==3u,verts,quads);
    if(v->section==1u) ml_ui_minirows(ui,v->squad,v->squad_count,cx+.009f,.626f,.306f,0,verts,quads);
    else if(v->section==2u) {
      char fact[64];snprintf(fact,sizeof(fact),"LEAGUE POSITION  %u",v->rank);
      ml_ui_text(ui,fact,cx+.018f,.632f,.284f,.030f,0,-2,0,1,verts,quads);
      snprintf(fact,sizeof(fact),"BOARD TARGET  TOP %u",v->board_target);
      ml_ui_text(ui,fact,cx+.018f,.680f,.284f,.025f,0,-3,0,1,verts,quads);
      ml_ui_text(ui,v->balance,cx+.018f,.742f,.284f,.0417f,0,-2,0,1,verts,quads);
    } else {
      ml_ui_minirows(ui,v->ranking,v->ranking_count,cx+.009f,.626f,.306f,1,verts,quads);
    }
    ml_ui_pills(ui,v->section,.872f,verts,quads);
  } else if (v->page==ML_PAGE_NEWS) {
    ml_ui_story(ui,slide,verts,quads);
  } else if(v->page==ML_PAGE_CALENDAR || v->page==ML_PAGE_ADVANCE) {
    ml_ui_calendar(ui,verts,quads);
  } else if(v->table_count) {
    ml_ui_table(ui,verts,quads);
  } else if(v->bracket_count) {
    ml_ui_bracket(ui,verts,quads);
  } else {
    ml_ui_primary(ui,verts,quads);
  }
  ml_ui_rect(ui,0,.925f,1,.075f,.025f,.10f,.28f,1,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0.f;
  if(v->page==ML_PAGE_ADVANCE) {
    ml_ui_rect(ui,.055f,.954f,.89f,.009f,.18f,.28f,.43f,1,-1,0,1,verts,quads);
    if(v->advance_progress>0.f)ml_ui_rect(ui,.055f,.954f,.89f*v->advance_progress,.009f,.07f,.77f,.70f,1,-1,0,1,verts,quads);
  }
  if(v->status[0] && !(v->drawer.open && v->drawer.modal)) {
    ml_ui_rect(ui,.06f,.166f,.88f,.035f,.25f,.035f,.025f,.97f,-1,0,1,verts,quads);
    ml_ui_text(ui,v->status,.073f,.172f,.85f,.023f,0,-1,0,1,verts,quads);
  }
  float hx=.047f;
  for(uint32_t i=0;i<v->helper_count;i++) {
    ui->helper_centers[i]=hx;
    const float text_width=measure_efootball_line_mode(v->helper_label[i],(int)strlen(v->helper_label[i]),22.f,EFOOTBALL_FONT_BOLD,0)/screen_width;
    ml_ui_text(ui,v->helper_label[i],hx+.021f,.9625f-11.f/screen_height,text_width+.003f,22.f/screen_height,0,-1,0,1,verts,quads);
    hx+=.021f+text_width+.047f;
  }
  ml_ui_toast(ui,verts,quads);
  ml_ui_confirmation(ui,verts,quads);
}

static void master_league_draw_layer(const MasterLeagueRender *ui,int overlay) {
  glUniform2f(gl.loc_off,0,0);
  for(uint32_t i=0;i<ui->draw_count;i++) {
    const MlDraw *d=&ui->draws[i];
    if((d->layer==1 || d->layer==3)!=overlay)continue;
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
static void master_league_draw(const MasterLeagueRender *ui) {
  master_league_draw_layer(ui,0);
}
