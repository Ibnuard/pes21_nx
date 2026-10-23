/* Small scene HUD; font, optical alignment and palette are shared with the
 * FootballNX frontend. All data is an immutable scalar snapshot. */
static void corner_tactics_helper(MasterLeagueRender *ui,const char *key,
    const char *label,float x,float cy,float width,GLfloat *verts,int *quads) {
  const float h=.045f,w=h*screen_height/screen_width;
  ml_ui_image(ui,switch_button_texture(key),0,x,cy-h*.5f,w,h,verts,quads);
  fd_text(ui,label,x+w+.005f,fd_cap_top(cy,.019f),width-w-.005f,
      .019f,-2,verts,quads);
}
static void corner_tactics_emit(MasterLeagueRender *ui,uint32_t pad,
    const FnxCornerView *view,int single,GLfloat *verts,int *quads) {
  if(!view->available || *quads>3584)return;
  float x=pad ? .615f : .035f;
  if(!view->open) {
    const char *hint=single ? "LS  CORNER TACTICS" : "<  CORNER TACTICS";
    ml_ui_rect(ui,x,.865f,.22f,.034f,.02f,.055f,.11f,.88f,-1,0,1,verts,quads);
    fd_center_text(ui,hint,x,.882f,.22f,.017f,-1,verts,quads);
    return;
  }
  const float y=.55f,w=.35f;
  ml_ui_rect(ui,x,y,w,.299f,.94f,.97f,1.f,.97f,-1,0,1,verts,quads);
  fd_rect(ui,x,y,w,.045f,.02f,.055f,.12f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=.012f*screen_height;
  /* Rounded top only: square the lower half before the continuous accent.
   * This removes the pale corner notches below the former rounded header. */
  fd_rect(ui,x,y+.020f,w,.025f,.02f,.055f,.12f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0;
  fd_rect(ui,x,y+.045f,w,.003f,.04f,.82f,.86f,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0;
  const char *title=view->mode==FNX_CORNER_DEFENCE ? "DEFENDING CORNER" :
      view->mode==FNX_CORNER_SHORT ? "SHORT CORNER" : "ATTACKING CORNER";
  fd_center_text(ui,title,x+.012f,y+.022f,w-.024f,.022f,-1,verts,quads);
  static const float dx[4]={.1025f,.193f,.1025f,.012f};
  static const float dy[4]={.064f,.127f,.190f,.127f};
  static const char *arrows[4]={"UP",">","DOWN","LEFT"};
  for(uint32_t d=0;d<4;d++) {
    const char *label=fnx_corner_label(view->mode,d);
    if(!label[0])continue;
    int selected=view->current==d;
    float cx=x+dx[d],cy=y+dy[d];
    fd_rect(ui,cx,cy,.145f,.054f,selected ? .015f : .06f,
        selected ? .42f : .10f,selected ? .87f : .17f,verts,quads);
    if(selected)fd_rect(ui,cx,cy,.003f,.054f,.08f,.94f,.86f,verts,quads);
    const float icon_h=.043f,icon_w=icon_h*screen_height/screen_width;
    ml_ui_image(ui,switch_button_texture(arrows[d]),0,cx+.006f,
        cy+(.054f-icon_h)*.5f,icon_w,icon_h,verts,quads);
    fd_text(ui,label,cx+.006f+icon_w+.005f,fd_cap_top(cy+.027f,.017f),
        .145f-icon_w-.020f,.017f,-1,verts,quads);
  }
  corner_tactics_helper(ui,"B_DARK","CLOSE",x+.032f,y+.272f,.12f,verts,quads);
  if(view->short_allowed)
    corner_tactics_helper(ui,"X_DARK",view->mode==FNX_CORNER_SHORT ?
        "ATTACKING CORNER" : "SHORT CORNER",x+.167f,y+.272f,.174f,verts,quads);
}
