/* Monthly ranking is a separate contract; legacy 14-day RP is never relabelled. */
enum { MO_RANK_PAGE_SIZE=50 };
static int monthly_snapshot_valid(const char *text) {
  if(!text[0])return 0;
  for(const unsigned char *p=(const unsigned char *)text;*p;p++)
    if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'||*p=='_'))return 0;
  return 1;
}
static void monthly_open(uint32_t section,uint32_t page,int tail) {
  if(!online.monthly_capable){message("LEAGUE RANKING","Monthly League Ranking has not been enabled by the server yet.");return;}
  char path[192];int reuse=(page>1||tail)&&section==online.rank_section&&online.rank_snapshot[0];
  snprintf(path,sizeof(path),"/ranking/monthly/%s?page=%u&page_size=%u%s%s",section?"past":"current",page,MO_RANK_PAGE_SIZE,reuse?"&snapshot_id=":"",reuse?online.rank_snapshot:"");
  if(request(J_MONTHLY,"GET",path,NULL,1)){
    online.rank_request_section=section;online.rank_request_page=page;online.rank_tail=(uint32_t)tail;
  }
}
static int monthly_period(const MjDoc *d,int obj,uint64_t *start,uint64_t *end,char *label,size_t size) {
  char id[16],expected[16];
  if(!field_text(d,obj,"season_id",id,sizeof(id))||!mj_u64(d,mj_get(d,obj,"starts_at_ms"),start)||
      !mj_u64(d,mj_get(d,obj,"ends_at_ms"),end)||*start<946659600000ULL||*end>253402189200000ULL||
      *start!=md_season_start(*start)||*end!=md_season_end(*start))return 0;
  md_season_text(*start,expected,sizeof(expected),1);if(strcmp(id,expected))return 0;
  md_season_text(*start,label,size,0);return 1;
}
static int parse_monthly(const MjDoc *d,int data) {
  uint32_t page,size,total;char scope[16],period[24],snapshot[65],label[40];uint64_t start,end;
  if(!field_text(d,data,"period",period,sizeof(period))||strcmp(period,"CALENDAR_MONTH")||
      !field_text(d,data,"scope",scope,sizeof(scope))||strcmp(scope,online.rank_request_section?"PAST":"CURRENT")||
      !field_text(d,data,"snapshot_id",snapshot,sizeof(snapshot))||!monthly_snapshot_valid(snapshot)||
      !required_u32(d,data,"page",&page)||page!=online.rank_request_page||!page||
      !required_u32(d,data,"page_size",&size)||size!=MO_RANK_PAGE_SIZE||
      !required_u32(d,data,"total",&total)||
      !monthly_period(d,mj_get(d,data,"season"),&start,&end,label,sizeof(label))||
      server_now()<start||server_now()>=end)return 0;
  if((page>1||online.rank_tail)&&strcmp(snapshot,online.rank_snapshot))return 0;
  uint64_t offset=(uint64_t)(page-1)*size;
  if(offset>total||(total&&offset==total))return 0;
  uint32_t count=total-(uint32_t)offset;if(count>size)count=size;
  int items=mj_get(d,data,"items");if(!mj_is(d,items,MJ_ARRAY)||d->tokens[items].count!=(int)count)return 0;
  MdRow rows[MO_RANK_PAGE_SIZE]={0};uint64_t last_season=start;
  for(uint32_t i=0;i<count;i++){
    int obj=mj_at(d,items,(int)i);MdRow *r=&rows[i];uint32_t rank,points,team;char name[64];
    if(!required_u32(d,obj,"rank",&rank)||rank!=(online.rank_request_section?1u:(uint32_t)offset+i+1)||
        !required_u32(d,obj,"club_id",&r->team_id)||!r->team_id||
        !required_u32(d,obj,"presentation_team_id",&team)||!team||
        !field_text(d,obj,"club_name",name,sizeof(name))||!name[0]||
        !required_u32(d,obj,"points",&points))return 0;
    r->badge=exhibition_team_catalog_badge(team);r->enabled=1;r->selected=r->team_id==strtoull(online.club_id,NULL,10);
    if(online.rank_request_section){
      uint64_t past_start,past_end;char month[40];
      if(!monthly_period(d,mj_get(d,obj,"season"),&past_start,&past_end,month,sizeof(month))||
          past_end>start||past_start>=last_season)return 0;
      last_season=past_start;copy(r->label,sizeof(r->label),name);snprintf(r->detail,sizeof(r->detail),"%s - CHAMPION",month);
    }else{
      uint32_t participation,podium;
      if(!required_u32(d,obj,"participation_points",&participation)||!required_u32(d,obj,"podium_points",&podium)||
          (uint64_t)participation+podium!=points||participation%500||podium%500)return 0;
      for(uint32_t j=0;j<i;j++)if(rows[j].team_id==r->team_id)return 0;
      snprintf(r->label,sizeof(r->label),"%u. %.49s",rank,name);
      snprintf(r->detail,sizeof(r->detail),"PARTICIPATION %u  +  PODIUM %u",participation,podium);
    }
    snprintf(r->value,sizeof(r->value),"%u PTS",points);
  }
  memcpy(online.rows,rows,count*sizeof(*rows));online.row_count=count;
  online.rank_section=online.rank_request_section;online.rank_page=page;online.rank_total=total;online.rank_ends=end;
  copy(online.rank_snapshot,sizeof(online.rank_snapshot),snapshot);copy(online.rank_season,sizeof(online.rank_season),label);
  return 1;
}
