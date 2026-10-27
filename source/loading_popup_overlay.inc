static void nx_loading_emit(MasterLeagueRender *ui,const NxLoadingView *v,
    uint64_t now_ms,GLfloat *verts,int *quads) {
  memset(ui,0,sizeof(*ui));if(!v->token)return;
  ml_ui_rect(ui,0,0,1,1,.015f,.035f,.09f,.74f,-1,0,1,verts,quads);
  ml_ui_panel(ui,v->title,ML_HEADER_MANAGER,.245f,.325f,.510f,.355f,0,verts,quads);
  /* A bounded 12-dot indicator reuses the existing rounded UI primitives. */
  for(uint32_t i=0;i<12;i++) {
    float angle=i*6.2831853f/12.f;
    uint32_t age=(i+12u-(uint32_t)(now_ms/80u)%12u)%12u;
    float strength=1.f-age/15.f;
    md_ui_circle(ui,.5f+cosf(angle)*.021f,.487f+sinf(angle)*.037f,
        .010f,.05f*strength,.55f*strength,.96f*strength,verts,quads);
  }
  fd_center_text(ui,v->message,.270f,.577f,.460f,.029f,-2,verts,quads);
  fd_center_text(ui,"PLEASE WAIT",.270f,.637f,.460f,.022f,-3,verts,quads);
}
