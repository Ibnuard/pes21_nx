/* Local preview of the agreed Asia/Jakarta calendar. A connected service must
 * own admission and timestamps; no device clock is authoritative online. */
#ifndef MANAGER_LEAGUE_DEV_CLOCK
#define MANAGER_LEAGUE_DEV_CLOCK 1
#endif
static uint64_t calendar_local_day(uint64_t stamp) {
  return stamp/MD_CALENDAR_DAY_MS+(stamp%MD_CALENDAR_DAY_MS+MD_LEAGUE_TIMEZONE_MS)/MD_CALENDAR_DAY_MS;
}
static uint32_t calendar_weekday(uint64_t stamp) {
  return (uint32_t)((calendar_local_day(stamp)+3u)%7u)+1u; /* Monday=1 */
}
static uint64_t calendar_midnight(uint64_t day) {
  return day*MD_CALENDAR_DAY_MS-MD_LEAGUE_TIMEZONE_MS;
}
static uint64_t calendar_preparation(uint64_t stamp,uint64_t previous_first) {
  uint64_t day=calendar_local_day(stamp);uint32_t weekday=calendar_weekday(stamp);
  if(weekday==2 || weekday==3)day+=4u-weekday;
  else if(weekday>=5)day+=8u-weekday;
  if(previous_first) {
    const uint64_t previous=calendar_local_day(previous_first)-1u;
    while(day<=previous)day+=(day+3u)%7u==0u ? 3u : 4u;
  }
  return calendar_midnight(day);
}
static uint64_t calendar_monday(const MdSave *s) {
  const uint64_t first=s->fixtures[0].kickoff_ms;
  return calendar_midnight(calendar_local_day(first)-(calendar_weekday(first)-1u));
}
static uint32_t fixture_day(const MdSave *s,const MdFixture *f) {
  return s->day_ms==MD_CALENDAR_DAY_MS ? calendar_weekday(f->kickoff_ms) :
      f->round<3 ? 4u : f->round<5 ? 5u : 6u;
}
static uint64_t competition_start(const MdSave *s) {
  const uint64_t first=s->fixtures[0].kickoff_ms;
  return s->day_ms==MD_CALENDAR_DAY_MS ? calendar_midnight(calendar_local_day(first)) : first;
}
static int development_clock_enabled(void) {return MANAGER_LEAGUE_DEV_CLOCK!=0;}
