/* Small scene HUD; font, optical alignment and palette are shared with the
 * FootballNX frontend. All data is an immutable scalar snapshot. */
static void corner_tactics_helper(MasterLeagueRender *ui,const char *key,
    const char *label,float x,float cy,float width,GLfloat *verts,int *quads) {
  const float h=.034f,w=h*screen_height/screen_width;
  ml_ui_image(ui,switch_button_texture(key),0,x,cy-h*.5f,w,h,verts,quads);
  fd_text(ui,label,x+w+.005f,fd_cap_top(cy,.017f),width-w-.005f,
      .017f,-2,verts,quads);
}
static void corner_tactics_emit(MasterLeagueRender *ui,uint32_t slot,
    uint32_t panels,const FnxCornerView *view,float progress,
    GLfloat *verts,int *quads) {
  if(!view->available || !view->open || *quads>3584 || slot>1)return;
  /* Keep each local owner's corner fixed, even if the other menu closes.
   * One-player uses the existing right helper edge; two-player uses both. */
  progress=fmaxf(0.f,fminf(1.f,progress));
  const float w=.26f,h=.215f,edge=.012f;
  const int left=panels>1 && slot==0;
  float x=(left ? edge : 1.f-edge-w)+
      (left ? -.006f : .006f)*(1.f-progress)*(1.f-progress);
  const float y=1.f-edge-h;
  ml_ui_rect(ui,x,y,w,h,.94f,.97f,1.f,.97f,-1,0,1,verts,quads);
  fd_rect(ui,x,y,w,.035f,.02f,.055f,.12f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=.012f*screen_height;
  /* Rounded top only: square the lower half before the continuous accent.
   * This removes the pale corner notches below the former rounded header. */
  fd_rect(ui,x,y+.0175f,w,.0175f,.02f,.055f,.12f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0;
  fd_rect(ui,x,y+.035f,w,.003f,.04f,.82f,.86f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0;
  const char *title=view->mode==FNX_CORNER_DEFENCE ? "DEFENDING CORNER" :
      view->mode==FNX_CORNER_SHORT ? "SHORT CORNER" : "ATTACKING CORNER";
  fd_center_text(ui,title,x+.010f,y+.0175f,w-.020f,.020f,-1,verts,quads);
  static const float dx[4]={.0735f,.137f,.0735f,.010f};
  static const float dy[4]={.047f,.091f,.135f,.091f};
  static const char *arrows[4]={"UP",">","DOWN","LEFT"};
  static const char *right_buttons[4]={"Y","X","A","B"};
  for(uint32_t d=0;d<4;d++) {
    const char *label=fnx_corner_label(view->mode,d);
    if(!label[0])continue;
    int selected=view->current==d;
    float cx=x+dx[d],cy=y+dy[d];
    fd_rect(ui,cx,cy,.113f,.039f,selected ? .015f : .06f,
        selected ? .42f : .10f,selected ? .87f : .17f,verts,quads);
    if(selected)fd_rect(ui,cx,cy,.003f,.039f,.08f,.94f,.86f,verts,quads);
    const float icon_h=.031f,icon_w=icon_h*screen_height/screen_width;
    ml_ui_image(ui,switch_button_texture(view->layout==2 ? right_buttons[d] : arrows[d]),0,cx+.006f,
        cy+(.039f-icon_h)*.5f,icon_w,icon_h,verts,quads);
    fd_text(ui,label,cx+.006f+icon_w+.005f,fd_cap_top(cy+.0195f,.017f),
        .113f-icon_w-.020f,.017f,-1,verts,quads);
  }
  corner_tactics_helper(ui,view->layout ? "SL" : "B_DARK",
      view->layout ? "HOLD L1" : "CLOSE",x+.012f,y+.190f,.085f,verts,quads);
  if(view->short_allowed)
    corner_tactics_helper(ui,view->layout ? "SR" : "X_DARK",view->mode==FNX_CORNER_SHORT ?
        "ATTACKING CORNER" : "SHORT CORNER",x+.117f,y+.190f,.132f,verts,quads);
}
