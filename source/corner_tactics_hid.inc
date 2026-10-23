static uint32_t corner_tactics_hid(uint32_t pad,uint64_t now,int allowed,
    int connected,uint32_t profile,u64 buttons,u64 menu_buttons,
    float x,float y,float rx,float ry) {
  FnxCornerView view;fnx_corner_view(pad,now,&view);
  uint32_t keys=0;
  const int full=profile==PES_CONTROLLER_PROFILE_FULL;
  if(full) {
    if(buttons&HidNpadButton_Up)keys|=FNX_CORNER_UP;
    if(buttons&HidNpadButton_Right)keys|=FNX_CORNER_RIGHT;
    if(buttons&HidNpadButton_Down)keys|=FNX_CORNER_DOWN;
    if(buttons&HidNpadButton_Left)keys|=FNX_CORNER_LEFT;
  } else {
    /* A horizontal Joy-Con has no spare D-pad. Stick click opens; after the
     * opening release, stick direction selects. SL+SR remains the taker. */
    if(buttons&(HidNpadButton_StickL|HidNpadButton_StickR))keys|=FNX_CORNER_LEFT;
    if(view.open) {
      if(y>.65f)keys|=FNX_CORNER_UP;
      if(y<-.65f)keys|=FNX_CORNER_DOWN;
      if(x>.65f)keys|=FNX_CORNER_RIGHT;
      if(x<-.65f)keys|=FNX_CORNER_LEFT;
    }
  }
  if(menu_buttons&HidNpadButton_B)keys|=FNX_CORNER_BACK;
  if(menu_buttons&HidNpadButton_X)keys|=FNX_CORNER_PAGE;
  const u64 known=full ? (HidNpadButton_Up|HidNpadButton_Right|
      HidNpadButton_Down|HidNpadButton_Left|HidNpadButton_B|HidNpadButton_X) :
      (HidNpadButton_StickL|HidNpadButton_StickR);
  if(full && (buttons&~known))keys|=FNX_CORNER_OTHER;
  if(!full && (buttons&(HidNpadButton_Plus|HidNpadButton_Minus|
      HidNpadButton_AnySL|HidNpadButton_AnySR)))keys|=FNX_CORNER_OTHER;
  if(!full && buttons && !keys)keys|=FNX_CORNER_OTHER;
  int neutral=fabsf(x)<.2f && fabsf(y)<.2f && fabsf(rx)<.2f && fabsf(ry)<.2f;
  return fnx_corner_input(pad,now,allowed,connected,keys,
                          neutral && !buttons);
}
