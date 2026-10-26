/* FootballNX match broadcast. Only projects the canonical dummy view; no I/O. */
static void md_watch_rule(MasterLeagueRender *ui,float x,float y,float w,float h,
    float r,float g,float b,float a,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x,y,w,h,r,g,b,a,-1,0,1,verts,quads);
  if(ui->draw_count)ui->draws[ui->draw_count-1u].round.radius=0;
}
static void md_watch_line(MasterLeagueRender *ui,float x0,float y0,float x1,float y1,
    float thickness,float r,float g,float b,float alpha,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,0);if(!d)return;
  d->color[0]=r;d->color[1]=g;d->color[2]=b;d->color[3]=alpha;
  *quads+=emit_segment(x0*screen_width,y0*screen_height,x1*screen_width,y1*screen_height,
      thickness*screen_height,verts+*quads*24);
  d->count=*quads-d->first;
}
static void md_watch_header(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_image(ui,gl.master_league_pearl_tex,0,0,0,1,1,verts,quads);
  char round[64];snprintf(round,sizeof(round),"MANAGER LEAGUE  -  ROUND %02u",v->round);
  fd_text(ui,round,.035f,.024f,.55f,.024f,-2,verts,quads);
  fd_text(ui,"LOCAL PREVIEW",.714f,.025f,.14f,.021f,-3,verts,quads);
  const char *status=v->watching_replay ? (v->paused ? "PAUSED" : "REPLAY") :
      v->phase==1 ? "LIVE" : v->phase==0 ? "PRE-MATCH" : "FULL TIME";
  fd_rect(ui,.858f,.018f,.112f,.036f,v->phase==1 && !v->watching_replay ? .89f : .03f,.10f,.22f,verts,quads);
  fd_center_text(ui,status,.862f,.036f,.104f,.022f,-1,verts,quads);
  fd_card(ui,.030f,.072f,.940f,.140f,0,0,verts,quads);
  ml_ui_art(ui,0,.030f,.072f,.335f,.140f,verts,quads);
  ml_ui_art(ui,1,.635f,.072f,.335f,.140f,verts,quads);
  if(v->home_badge)ml_ui_image(ui,gl.badge_tex,v->home_badge,.050f,.101f,.043f,.076f,verts,quads);
  if(v->away_badge)ml_ui_image(ui,gl.badge_tex,v->away_badge,.902f,.101f,.043f,.076f,verts,quads);
  fd_text(ui,v->home,.109f,fd_cap_top(.128f,.0333f),.239f,.0333f,-1,verts,quads);
  fd_text(ui,v->away,.654f,fd_cap_top(.128f,.0333f),.232f,.0333f,-1,verts,quads);
  fd_text(ui,"HOME",.109f,.173f,.22f,.0208f,-1,verts,quads);
  fd_text(ui,"AWAY",.654f,.173f,.22f,.0208f,-1,verts,quads);
  fd_center_text(ui,v->score,.365f,.127f,.270f,.068f,-2,verts,quads);
  fd_center_text(ui,v->clock,.365f,.186f,.270f,.029f,-2,verts,quads);
  md_watch_rule(ui,.365f,.073f,.135f,.004f,.04f,.35f,.92f,1,verts,quads);
  md_watch_rule(ui,.500f,.073f,.135f,.004f,.94f,.12f,.25f,1,verts,quads);
}
static void md_watch_pitch(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  const float x=.058f,y=.279f,w=.604f,h=.548f;
  fd_card(ui,.030f,.235f,.665f,.662f,0,0,verts,quads);
  ml_ui_art(ui,2,.030f,.235f,.665f,.662f,verts,quads);
  fd_text(ui,"TACTICAL VIEW",.050f,.249f,.23f,.021f,-1,verts,quads);
  md_ui_circle(ui,.479f,.259f,.011f,.07f,.42f,.98f,verts,quads);
  fd_text(ui,"HOME",.491f,.249f,.062f,.018f,-1,verts,quads);
  md_ui_circle(ui,.576f,.259f,.011f,.97f,.16f,.27f,verts,quads);
  fd_text(ui,"AWAY",.589f,.249f,.063f,.018f,-1,verts,quads);
  fd_rect(ui,x-.009f,y-.009f,w+.018f,h+.018f,.016f,.10f,.12f,verts,quads);
  fd_rect(ui,x,y,w,h,.043f,.22f,.17f,verts,quads);
  for(uint32_t i=0;i<12;i++) {
    const float shade=i%2 ? .018f : 0.f;
    md_watch_rule(ui,x+i*w/12,y,w/12,h,.043f+shade,.22f+shade,.17f+shade,1,verts,quads);
  }
  /* Subtle tactical grid is subordinate to the regulation field markings. */
  for(uint32_t i=1;i<6;i++)md_watch_rule(ui,x+w*i/6,y,.0007f,h,.43f,.75f,.67f,.10f,verts,quads);
  for(uint32_t i=1;i<4;i++)md_watch_rule(ui,x,y+h*i/4,w,.0012f,.43f,.75f,.67f,.10f,verts,quads);
  const float line=.0016f,edge=.010f;
  md_watch_rule(ui,x+edge,y+.014f,w-2*edge,.0023f,.70f,.87f,.81f,.82f,verts,quads);
  md_watch_rule(ui,x+edge,y+h-.0163f,w-2*edge,.0023f,.70f,.87f,.81f,.82f,verts,quads);
  md_watch_rule(ui,x+edge,y+.014f,line,h-.028f,.70f,.87f,.81f,.82f,verts,quads);
  md_watch_rule(ui,x+w-edge-line,y+.014f,line,h-.028f,.70f,.87f,.81f,.82f,verts,quads);
  md_watch_rule(ui,x+w*.5f,y+.014f,line,h-.028f,.70f,.87f,.81f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.218f,.64f,.82f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.210f,.061f,.238f,.188f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,.006f,.82f,.93f,.87f,verts,quads);
  for(uint32_t side=0;side<2;side++) {
    const float bx=side ? x+w-edge-w*.16f : x+edge;
    md_watch_rule(ui,bx,y+h*.23f,w*.16f,.0023f,.70f,.87f,.81f,.82f,verts,quads);
    md_watch_rule(ui,bx,y+h*.77f,w*.16f,.0023f,.70f,.87f,.81f,.82f,verts,quads);
    md_watch_rule(ui,side ? bx : bx+w*.16f,y+h*.23f,line,h*.54f,.70f,.87f,.81f,.82f,verts,quads);
    const float small=side ? x+w-edge-w*.055f : x+edge;
    md_watch_rule(ui,small,y+h*.38f,w*.055f,.0023f,.70f,.87f,.81f,.82f,verts,quads);
    md_watch_rule(ui,small,y+h*.62f,w*.055f,.0023f,.70f,.87f,.81f,.82f,verts,quads);
    md_watch_rule(ui,side ? small : small+w*.055f,y+h*.38f,line,h*.24f,.70f,.87f,.81f,.82f,verts,quads);
    const float gx=side ? x+w-edge : x;
    for(uint32_t n=0;n<4;n++)md_watch_rule(ui,gx+n*.0024f,y+h*.442f,.0006f,h*.116f,.75f,.87f,.85f,.55f,verts,quads);
    for(uint32_t n=0;n<5;n++)md_watch_rule(ui,gx,y+h*(.442f+n*.029f),.009f,.0010f,.75f,.87f,.85f,.55f,verts,quads);
    md_ui_circle(ui,side ? x+w*.89f : x+w*.11f,y+h*.5f,.005f,.82f,.93f,.87f,verts,quads);
  }
  if(v->phase || v->watching_replay)for(uint32_t n=0;n<5;n++) {
    const MdDot *a=n ? &v->ball_trail[n-1] : &v->dots[22],*b=&v->ball_trail[n];
    /* A new episode can relocate the ball; never draw across that discontinuity. */
    if(fabsf(a->x-b->x)+fabsf(a->y-b->y)>.22f)break;
    md_watch_line(ui,x+.018f+a->x*(w-.036f),y+.025f+a->y*(h-.05f),
        x+.018f+b->x*(w-.036f),y+.025f+b->y*(h-.05f),.0026f,.89f,.94f,.73f,(5-n)*.12f,verts,quads);
  }
  for(uint32_t i=0;i<23;i++) {
    const MdDot *d=&v->dots[i];const float cx=x+.018f+d->x*(w-.036f),cy=y+.025f+d->y*(h-.05f);
    const float size=i==22 ? .019f : .027f;
    md_ui_circle(ui,cx+.001f,cy+.004f,size+.006f,.015f,.095f,.09f,verts,quads);
    if(i==22) {
      const float pulse=.039f+.005f*sinf(v->elapsed_ms*.008f);
      md_ui_circle(ui,cx,cy,pulse,.25f,.47f,.37f,verts,quads);
      md_ui_circle(ui,cx,cy,size+.007f,.99f,.80f,.30f,verts,quads);
      md_ui_circle(ui,cx,cy,size,.99f,1.f,.96f,verts,quads);
    } else {
      md_ui_circle(ui,cx,cy,size+.004f,.88f,.95f,.98f,verts,quads);
      md_ui_circle(ui,cx,cy,size,d->side ? .96f : .04f,d->side ? .13f : .36f,d->side ? .25f : .96f,verts,quads);
      char number[8];snprintf(number,sizeof(number),"%u",d->number);
      fd_center_text(ui,number,cx-.015f,cy,.030f,.020f,-1,verts,quads);
    }
  }
}
static void md_watch_timeline(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  const float x=.063f,y=.864f,w=.595f;
  md_watch_rule(ui,x,y,w,.0035f,.55f,.67f,.76f,.65f,verts,quads);
  if(v->elapsed_ms)md_watch_rule(ui,x,y,w*v->elapsed_ms/MD_DURATION,.0035f,.13f,.80f,.95f,1,verts,quads);
  for(uint32_t i=0;i<v->timeline_count;i++) {
    const MdTimelineMark *mark=&v->timeline[i];const float xx=x+w*mark->at_ms/MD_DURATION;
    if(mark->kind==MD_YELLOW)fd_rect(ui,xx-.0025f,y-.006f,.005f,.014f,1,.85f,.20f,verts,quads);
    else if(mark->kind==MD_SUB)md_watch_rule(ui,xx-.002f,y-.005f,.004f,.013f,.20f,.94f,.72f,1,verts,quads);
    else md_ui_circle(ui,xx,y+.001f,mark->kind==MD_GOAL ? .013f : .008f,1,1,1,verts,quads);
  }
  md_ui_circle(ui,x+w*v->elapsed_ms/MD_DURATION,y+.001f,.010f,.12f,.81f,.97f,verts,quads);
  fd_text(ui,"0'",x,.877f,.06f,.0208f,-1,verts,quads);
  fd_center_text(ui,"45'",x+w*.5f-.03f,.886f,.06f,.0208f,-1,verts,quads);
  fd_text(ui,"90'",x+w-.025f,.877f,.04f,.0208f,-1,verts,quads);
}
static void md_watch_stats(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  fd_card(ui,.718f,.235f,.252f,.417f,0,0,verts,quads);
  ml_ui_art(ui,0,.718f,.235f,.252f,.060f,verts,quads);
  ml_ui_header_icon(ui,ML_HEADER_STATISTICS,.732f,.247f,.032f,verts,quads);
  fd_text(ui,"MATCH STATS",.761f,.250f,.19f,.025f,-1,verts,quads);
  static const char *const labels[]={"SHOTS","ON TARGET","FOULS","CORNERS","YELLOW CARDS","SUBSTITUTIONS"};
  const uint32_t *values[]={v->shots,v->on_target,v->fouls,v->corners,v->cards,v->substitutions};
  for(uint32_t i=0;i<6;i++) {
    const float y=.311f+i*.054f;char a[12],b[12];
    snprintf(a,sizeof(a),"%u",values[i][0]);snprintf(b,sizeof(b),"%u",values[i][1]);
    fd_text(ui,a,.735f,y,.035f,.028f,-2,verts,quads);
    fd_text(ui,b,.929f,y,.028f,.028f,-2,verts,quads);
    fd_center_text(ui,labels[i],.774f,y+.012f,.149f,.019f,-3,verts,quads);
    const uint32_t total=values[i][0]+values[i][1];
    md_watch_rule(ui,.737f,y+.034f,.214f,.005f,.87f,.91f,.95f,1,verts,quads);
    if(total) {
      const float blue=.214f*values[i][0]/total,red=.214f-blue;
      if(blue>0)md_watch_rule(ui,.737f,y+.034f,blue,.005f,.04f,.36f,.96f,1,verts,quads);
      if(red>0)md_watch_rule(ui,.737f+blue,y+.034f,red,.005f,.94f,.12f,.25f,1,verts,quads);
    }
  }
  fd_card(ui,.718f,.675f,.252f,.222f,0,0,verts,quads);
  fd_text(ui,"TOUCHLINE",.735f,.692f,.21f,.025f,-2,verts,quads);
  md_watch_rule(ui,.735f,.730f,.218f,.0013f,.85f,.90f,.95f,1,verts,quads);
  for(uint32_t i=0;i<3;i++)if(v->event_feed[i].label[0]) {
    float y=.744f+i*.050f;
    md_watch_rule(ui,.735f,y+.003f,.003f,.033f,i ? .64f : .04f,i ? .71f : .36f,i ? .80f : .96f,1,verts,quads);
    fd_text(ui,v->event_feed[i].label,.746f,y,.205f,.0236f,-2,verts,quads);
    fd_text(ui,v->event_feed[i].detail,.746f,y+.027f,.205f,.0208f,-3,verts,quads);
  }
  if(!v->event_feed[0].label[0]) {
    fd_text(ui,"THE STAGE IS SET",.738f,.767f,.21f,.026f,-2,verts,quads);
    fd_text(ui,"Waiting for the opening whistle",.738f,.813f,.21f,.021f,-3,verts,quads);
  }
}
static void md_watch_event(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  if(v->event_age_ms>=2400 || v->event_kind==MD_PASS || v->event_kind>MD_HALF)return;
  static const char *const labels[]={"","WIDE","GOAL","FOUL","CARD","SUB","OFFSIDE","CORNER","SAVE","HALF TIME"};
  const float raw=fminf(1.f,v->event_age_ms/260.f),travel=(1-raw)*(1-raw)*(1-raw);
  const float x=.126f,y=.650f+travel*.038f,w=.465f,h=.138f;
  fd_card(ui,x,y,w,h,0,0,verts,quads);
  ml_ui_art(ui,v->event_side ? 1 : 0,x,y,.145f,h,verts,quads);
  if(v->event_kind==MD_YELLOW)fd_rect(ui,x+.112f,y+.018f,.017f,.039f,1,.85f,.16f,verts,quads);
  fd_center_text(ui,labels[v->event_kind],x+.012f,y+.075f,.122f,v->event_kind==MD_HALF ? .028f : .041f,-1,verts,quads);
  char minute[16];snprintf(minute,sizeof(minute),"%u'",(v->elapsed_ms-v->event_age_ms)/2000u);
  fd_text(ui,minute,x+.017f,y+.014f,.08f,.020f,-1,verts,quads);
  const uint32_t badge=v->event_kind==MD_HALF ? 0 : v->event_side ? v->away_badge : v->home_badge;
  if(badge)ml_ui_image(ui,gl.badge_tex,badge,x+.159f,y+.035f,.035f,.062f,verts,quads);
  fd_text(ui,v->event_kind==MD_HALF ? "FIRST HALF COMPLETE" : v->event_side ? v->away : v->home,
      x+.208f,y+.031f,.242f,.028f,-2,verts,quads);
  char detail[64];
  if(v->event_kind==MD_SUB)snprintf(detail,sizeof(detail),"#%u OFF    >    #%u ON",v->event_player,v->event_other);
  else if(v->event_kind==MD_HALF)snprintf(detail,sizeof(detail),"%s AT THE BREAK",v->score);
  else snprintf(detail,sizeof(detail),"%.47s",v->event_name);
  fd_text(ui,detail,x+.208f,y+.082f,.242f,.023f,-3,verts,quads);
  if(v->event_kind==MD_SUB) {
    md_watch_rule(ui,x+.208f,y+h-.011f,.052f,.0035f,.93f,.14f,.25f,1,verts,quads);
    md_watch_rule(ui,x+.269f,y+h-.011f,.052f,.0035f,.06f,.74f,.52f,1,verts,quads);
  }
}
static void md_watch_emit(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  md_watch_header(ui,v,verts,quads);
  md_watch_pitch(ui,v,verts,quads);
  md_watch_timeline(ui,v,verts,quads);
  md_watch_stats(ui,v,verts,quads);
  md_watch_event(ui,v,verts,quads);
}
