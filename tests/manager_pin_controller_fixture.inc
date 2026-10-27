/* Drive the production keypad through public controller events. */
static void test_pin_key(uint32_t target) {
  MdView v;manager_dummy_view(&v);assert(v.pin_open);
  while(v.pin_cursor/3>target/3){manager_dummy_pad(1024);manager_dummy_view(&v);}
  while(v.pin_cursor/3<target/3){manager_dummy_pad(2048);manager_dummy_view(&v);}
  while(v.pin_cursor%3>target%3){manager_dummy_pad(4096);manager_dummy_view(&v);}
  while(v.pin_cursor%3<target%3){manager_dummy_pad(8192);manager_dummy_view(&v);}
  assert(v.pin_cursor==target);manager_dummy_pad(2);
}
static void test_pin_digits(const char *pin) {
  for(uint32_t i=0;i<4;i++)test_pin_key(pin[i]=='0' ? 10u : (uint32_t)(pin[i]-'1'));
  test_pin_key(11);
}
static void test_enter_pin(const char *pin,int creating) {
  manager_dummy_pad(2);test_pin_digits(pin);
  if(creating)test_pin_digits(pin);
  MdView v;manager_dummy_view(&v);assert(!v.pin_open);
}
