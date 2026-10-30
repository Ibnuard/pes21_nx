static void registration_clubs_v120(void) {
  online.active=1;online.compatible=1;online.page=MD_REGISTER;online.focus=1;
  manager_online_pad(A);assert(online.page==MD_LEAGUES);
  const uint32_t leagues=manager_club_category_count();assert(leagues>0 && leagues<EXHIBITION_TEAM_CATEGORY_COUNT);
  MdView v;
  manager_online_pad(R);assert(online.focus==(leagues>5?5:leagues-1));
  manager_online_pad(L);assert(online.focus==0);
  uint32_t clubs=0,nations=0;
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++) {
    const ExhibitionTeamCategory *c=&exhibition_team_categories[i];
    if(!manager_club_category(i)) {
      for(uint32_t j=0;j<c->team_count;j++){assert(!manager_club_team_allowed(c->teams[j]));nations++;}
      continue;
    }
    online.page=MD_LEAGUES;online.focus=manager_club_category_ordinal(i);
    manager_online_view(&v);assert(v.picker_category==i && v.total==leagues && v.count && v.rows[v.focus-v.first].badge==c->badge_slot);
    assert(!v.rows[v.focus-v.first].detail[0]);
    manager_online_pad(A);assert(online.page==MD_CLUB && online.category==i);
    manager_online_pad(R);assert(online.club_choice==(c->team_count>5?5:c->team_count-1));
    manager_online_pad(L);assert(online.club_choice==0);
    for(uint32_t j=0;j<c->team_count;j++) {
      online.club_choice=j;manager_online_view(&v);
      assert(v.focus==j && !strcmp(v.rows[j-v.first].label,exhibition_team_catalog_name(c->teams[j])));
      assert(manager_club_team_allowed(c->teams[j]));clubs++;
    }
    const uint32_t choice=online.club_choice;
    manager_online_pad(A);assert(online.page==MD_NAME && online.team==c->teams[choice]);
    manager_online_pad(B);assert(online.page==MD_CLUB && online.club_choice==choice);
    manager_online_pad(B);assert(online.page==MD_LEAGUES && online.focus==manager_club_category_ordinal(i));
  }
  assert(clubs && nations && !manager_club_team_allowed(UINT32_MAX));
  manager_online_pad(B);assert(online.page==MD_REGISTER && online.focus==1);
  online.auth_register=1;copy(online.login_id,sizeof(online.login_id),"picker_test");
  copy(online.club_name,sizeof(online.club_name),"Test Club");pin_confirmed=1;
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++)if(!manager_club_category(i)){
    online.team=exhibition_team_categories[i].teams[0];break;
  }
  auth_submit();assert(online.notice[0] && !online.busy);
}
