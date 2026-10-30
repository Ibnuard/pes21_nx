#ifndef PESNX_MANAGER_LEAGUE_SEASON_H
#define PESNX_MANAGER_LEAGUE_SEASON_H
#include <stdint.h>
#include <time.h>
#include <stdio.h>

/* Calendar months in WIB, independent of the device timezone. */
static inline uint64_t md_season_start(uint64_t ms) {
  time_t seconds=(time_t)(ms/1000u+25200u);struct tm date;
  if(!gmtime_r(&seconds,&date))return 0;
  uint64_t day=(ms+UINT64_C(25200000))/86400000u;
  return (day-(uint32_t)(date.tm_mday-1))*UINT64_C(86400000)-25200000u;
}
static inline uint64_t md_season_end(uint64_t ms) {
  static const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
  time_t seconds=(time_t)(ms/1000u+25200u);struct tm date;
  if(!gmtime_r(&seconds,&date))return 0;
  unsigned year=(unsigned)date.tm_year+1900, count=days[date.tm_mon];
  if(date.tm_mon==1&&year%4==0&&(year%100!=0||year%400==0))count++;
  return md_season_start(ms)+count*UINT64_C(86400000);
}
static inline void md_season_text(uint64_t ms,char *out,size_t size,int id) {
  time_t seconds=(time_t)(ms/1000u+25200u);struct tm date;
  if(gmtime_r(&seconds,&date))strftime(out,size,id?"%Y-%m":"%B %Y",&date);
  else if(size)out[0]=0;
}
static inline uint32_t md_season_prize(uint32_t rank) {
  return rank==1?2000u:rank==2?1500u:rank==3?1000u:0u;
}
#endif
