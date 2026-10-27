/* Controller-only PIN entry. Raw digits never enter MdView or a save record. */
static uint32_t pin_active,pin_cursor,pin_length,pin_confirming,pin_creating,pin_confirmed;
static char pin_value[5],pin_first[5],pin_buffer[5];
static void pin_close(void) {
  pin_active=pin_cursor=pin_length=pin_confirming=pin_creating=0;
  md_auth_wipe(pin_first,sizeof(pin_first));md_auth_wipe(pin_buffer,sizeof(pin_buffer));
}
static void pin_clear(void) {
  pin_close();pin_confirmed=0;md_auth_wipe(pin_value,sizeof(pin_value));
}
static void pin_open(uint32_t creating) {
  pin_clear();pin_active=1;pin_creating=creating;notice[0]=0;
}
static void pin_backspace(void) {
  if(pin_length)pin_buffer[--pin_length]=0;
  if(pin_cursor==11)pin_cursor=10;
  notice[0]=0;
}
static void pin_pad(uint32_t key) {
  if(key&B){pin_clear();notice[0]=0;return;}
  if(key&X){pin_backspace();return;}
  const uint32_t old=pin_cursor;
  if(key&UP){if(pin_cursor>=3)pin_cursor-=3;}
  else if(key&DOWN){if(pin_cursor<9)pin_cursor+=3;}
  else if(key&LEFT){if(pin_cursor%3)pin_cursor--;}
  else if(key&RIGHT){if(pin_cursor%3<2)pin_cursor++;}
  if(pin_cursor==11 && pin_length!=4)pin_cursor=old==8 ? 10 : old;
  if(!(key&A))return;
  if(pin_cursor==9){pin_backspace();return;}
  if(pin_cursor==11) {
    if(!md_auth_pin_valid(pin_buffer))return;
    if(pin_creating && !pin_confirming) {
      memcpy(pin_first,pin_buffer,sizeof(pin_first));md_auth_wipe(pin_buffer,sizeof(pin_buffer));
      pin_length=0;pin_confirming=1;pin_cursor=0;notice[0]=0;
    } else if(pin_creating && strcmp(pin_first,pin_buffer)) {
      md_auth_wipe(pin_buffer,sizeof(pin_buffer));pin_length=0;pin_cursor=0;
      snprintf(notice,sizeof(notice),"PINs do not match. Enter the same four digits again.");
    } else {
      memcpy(pin_value,pin_buffer,sizeof(pin_value));pin_confirmed=1;pin_close();notice[0]=0;
    }
    return;
  }
  if(pin_length<4) {
    pin_buffer[pin_length++]=(char)(pin_cursor==10 ? '0' : '1'+pin_cursor);
    pin_buffer[pin_length]=0;notice[0]=0;
  }
}
