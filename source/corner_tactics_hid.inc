static uint32_t corner_tactics_hid(uint32_t pad,uint64_t now,int allowed,
    int connected,uint32_t profile,u64 buttons,u64 menu_buttons,
    float x,float y,float rx,float ry) {
  uint32_t keys=0;
  const int full=profile==PES_CONTROLLER_PROFILE_FULL;
  int neutral=fabsf(x)<.2f && fabsf(y)<.2f && fabsf(rx)<.2f && fabsf(ry)<.2f;
  if(!full) {
    const u64 left=HidNpadButton_L|HidNpadButton_AnySL;
    const u64 right=HidNpadButton_R|HidNpadButton_AnySR;
    /* menu_buttons already rotates each horizontal grip into spatial
     * X=up/A=right/B=down/Y=left. Do not use the analogue stick as a button. */
    if(buttons&left)keys|=FNX_CORNER_HOLD;
    if(buttons&right)keys|=FNX_CORNER_PAGE;
    if(menu_buttons&HidNpadButton_X)keys|=FNX_CORNER_UP;
    if(menu_buttons&HidNpadButton_A)keys|=FNX_CORNER_RIGHT;
    if(menu_buttons&HidNpadButton_B)keys|=FNX_CORNER_DOWN;
    if(menu_buttons&HidNpadButton_Y)keys|=FNX_CORNER_LEFT;
    const u64 known=left|right|HidNpadButton_Up|HidNpadButton_Right|
        HidNpadButton_Down|HidNpadButton_Left|HidNpadButton_A|
        HidNpadButton_B|HidNpadButton_X|HidNpadButton_Y;
    if(buttons&~known)keys|=FNX_CORNER_OTHER;
    return fnx_corner_hold_input(pad,now,allowed,connected,keys,
                                neutral && !buttons,profile);
  }
  if(full) {
    if(buttons&HidNpadButton_Up)keys|=FNX_CORNER_UP;
    if(buttons&HidNpadButton_Right)keys|=FNX_CORNER_RIGHT;
    if(buttons&HidNpadButton_Down)keys|=FNX_CORNER_DOWN;
    if(buttons&HidNpadButton_Left)keys|=FNX_CORNER_LEFT;
  }
  if(menu_buttons&HidNpadButton_B)keys|=FNX_CORNER_BACK;
  if(menu_buttons&HidNpadButton_X)keys|=FNX_CORNER_PAGE;
  const u64 known=HidNpadButton_Up|HidNpadButton_Right|
      HidNpadButton_Down|HidNpadButton_Left|HidNpadButton_B|HidNpadButton_X;
  if(buttons&~known)keys|=FNX_CORNER_OTHER;
  return fnx_corner_input(pad,now,allowed,connected,keys,
                          neutral && !buttons);
}
