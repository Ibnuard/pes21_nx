/* Activity contains already-published records only. It never derives transfers
 * from offer pools or leaks precomputed results before their broadcast. */
static void feed_identity(const MjDoc *d,int object,MdRow *r){
  char key[64]="";field_text(d,object,"player_key",key,sizeof(key));r->identity=identity(key);
  const MlCatalogPlayer *p=ml_catalog_find_identity(r->identity);
  if(p){r->portrait=p->portrait_id;r->native_id=p->native_id;}
}
static int parse_club_feed(const MjDoc *d,int data){
  int list=mj_is(d,data,MJ_OBJECT)?mj_get(d,data,"items"):data;
  if(mj_is(d,list,MJ_NULL)){online.activity_count=online.row_count=online.news_count=0;return 1;}
  if(!mj_is(d,list,MJ_ARRAY)||d->tokens[list].count>MO_MATCHES)return 0;
  MdFeedItem *items=calloc(MO_MATCHES,sizeof(*items));if(!items)return 0;
  uint32_t count=0;int ok=1;
  for(int i=0;i<d->tokens[list].count;i++){
    int object=mj_at(d,list,i),p=mj_get(d,object,"parameters");char type[48]="",club[64]="",name[64]="",week[12]="";
    field_text(d,object,"type",type,sizeof(type));if(p<0)p=object;
    MdFeedItem *f=&items[count];f->at_ms=field_u64(d,object,"occurred_at_ms");
    if(f->at_ms>server_now())continue;
    field_text(d,p,"club_name",club,sizeof(club));field_text(d,p,"player_name",name,sizeof(name));field_text(d,object,"league_label",week,sizeof(week));
    f->row.enabled=1;f->row.team_id=(uint32_t)field_u64(d,p,"club_id");
    f->row.badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,p,"presentation_team_id"));feed_identity(d,p,&f->row);
    if(!strcmp(type,"PLAYER_SIGNED")||!strcmp(type,"PACK_PURCHASE")){
      copy(f->row.label,sizeof(f->row.label),"NEW SIGNING");
      if(club[0]&&name[0])snprintf(f->body,sizeof(f->body),"%s signs %s.",club,name);
      else snprintf(f->body,sizeof(f->body),"%s completed a player signing.",club[0]?club:"A league club");
    }else if(!strcmp(type,"MATCH_RESULT")){
      char away[64]="",home[64]="";uint32_t hg,ag;field_text(d,p,"home_club_name",home,sizeof(home));field_text(d,p,"away_club_name",away,sizeof(away));
      copy(f->row.label,sizeof(f->row.label),"MATCH RESULT");
      if(home[0]&&away[0]&&required_u32(d,p,"home_goals",&hg)&&required_u32(d,p,"away_goals",&ag)&&hg<100&&ag<100){
        snprintf(f->body,sizeof(f->body),"%s  %u - %u  %s",home,hg,ag,away);
        f->row.badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,p,"home_presentation_team_id"));f->row.away_badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,p,"away_presentation_team_id"));
      }else copy(f->body,sizeof(f->body),"A match result has been published. Open Match Centre for the score.");
    }else if(!strcmp(type,"LEAGUE_LEADER")){
      uint32_t points;copy(f->row.label,sizeof(f->row.label),"LEAGUE LEADER");
      if(!club[0]||!required_u32(d,p,"league_points",&points)){ok=0;break;}
      snprintf(f->body,sizeof(f->body),"%s leads the table with %u League Points.",club,points);
    }else {
      copy(f->row.label,sizeof(f->row.label),"CLUB NEWS");
      if(!field_text(d,object,"summary",f->body,sizeof(f->body)))snprintf(f->body,sizeof(f->body),"%s",club[0]?club:"League activity has been published.");
    }
    char date[48]="";if(f->at_ms)format_date(f->at_ms,date,sizeof(date));
    snprintf(f->context,sizeof(f->context),"%s%s%s",week,week[0]&&date[0]?" - ":"",date);
    snprintf(f->row.detail,sizeof(f->row.detail),"%.95s",f->body);copy(f->row.value,sizeof(f->row.value),week);count++;
  }
  if(ok){
    /* Stable newest-first order, including legacy responses without timestamps. */
    for(uint32_t i=1;i<count;i++){MdFeedItem x=items[i];uint32_t j=i;while(j&&items[j-1].at_ms<x.at_ms){items[j]=items[j-1];j--;}items[j]=x;}
    memcpy(online.activity,items,count*sizeof(*items));online.activity_count=online.row_count=online.news_count=count;
    for(uint32_t i=0;i<count;i++)online.news[i]=online.rows[i]=items[i].row;
  }
  free(items);return ok;
}
static int parse_player_feed(const MjDoc *d,int data){
  if(!mj_is(d,data,MJ_OBJECT)||field_u64(d,data,"cycle_id")!=online.cycle)return 0;
  uint64_t published=field_u64(d,data,"published_through_ms");if(!published||published>server_now())return 0;
  MdFeedItem (*items)[32]=calloc(2,sizeof(*items));if(!items)return 0;
  uint32_t counts[2]={0,0};int ok=1;
  for(unsigned section=0;section<2&&ok;section++){
    int list=mj_get(d,data,section?"rising_stars":"top_scorers");
    if(!mj_is(d,list,MJ_ARRAY)||d->tokens[list].count>32){ok=0;break;}
    for(int i=0;i<d->tokens[list].count;i++){
      int obj=mj_at(d,list,i);MdFeedItem *f=&items[section][i];uint32_t goals,assists,ovr;char club[64];
      feed_identity(d,obj,&f->row);
      if(!f->row.identity||!field_text(d,obj,"player_name",f->row.label,sizeof(f->row.label))||!field_text(d,obj,"club_name",club,sizeof(club))||
          !required_u32(d,obj,"goals",&goals)||goals>1000||!required_u32(d,obj,"assists",&assists)||assists>1000||!required_u32(d,obj,"snapshot_ovr",&ovr)||!ovr||ovr>99||
          (!section&&!goals)||(section&&(ovr>69||!(goals+assists)))){ok=0;break;}
      for(int j=0;j<i;j++)if(items[section][j].row.identity==f->row.identity){ok=0;break;}
      if(!ok)break;
      f->row.badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,obj,"presentation_team_id"));f->row.rating=ovr;f->row.enabled=1;
      f->goals=goals;f->assists=assists;f->assists_known=1;
      copy(f->body,sizeof(f->body),club);
      snprintf(f->context,sizeof(f->context),"#%u  %s",(unsigned)i+1,section?"RISING STAR":"TOP SCORER");
      counts[section]++;
    }
  }
  if(ok){memcpy(online.player_feed,items,sizeof(online.player_feed));memcpy(online.player_feed_count,counts,sizeof(counts));}
  free(items);return ok;
}
