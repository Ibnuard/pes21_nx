static uint32_t previous[2];
static void setup(void) {
  match_squad_data_get_formation = mock_get_formation;
  match_squad_data_set_formation = mock_set_formation;
  match_formation_copy_assign = mock_copy_formation;
  match_formation_get_position = mock_position;
  match_formation_set_position = mock_set_position;
  match_formation_get_role = mock_role;
  match_formation_set_role = mock_set_role;
  match_squad_data_set_player_role_position = mock_set_player_role;
  for (uint32_t side = 0; side < 2; side++) {
    PrematchGameplanSide *s = &exhibition_gameplan_sides[side];
    prematch_gameplan_reset_side(s);
    s->squad_data = &mock_squads[side];
    s->field_count = 11;
    s->bench_count = 1;
    s->player_count = 12;
    s->page = PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE;
    for (uint32_t i = 0; i < 12; i++) {
      s->players[i].order_no = s->players[i].member_id = i;
      s->players[i].starting = i < 11;
    }
    // Reverse outfield slot ordering to catch presets that equate order with role.
    for (uint32_t i = 0; i < 11; i++) {
      uint32_t slot = i ? 11 - i : 0;
      const PrematchFormationPreset *p = &prematch_formation_presets[0];
      uint8_t pos[2] = {p->y[slot], p->x[slot]};
      mock_set_position(&mock_squads[side].formation[0], i, pos, 0);
      mock_set_role(&mock_squads[side].formation[0], i, p->role[slot], 0);
    }
    mock_squads[side].formation[1] = mock_squads[side].formation[0];
    s->default_formation[0] = mock_squads[side].formation[0];
    s->default_formation[1] = mock_squads[side].formation[1];
    s->default_formation_valid = 1;
    prematch_gameplan_refresh_side(side);
    previous[side] = PES_GAMEPLAN_BUTTON_CONNECTED;
    pes_controller_custom_prematch_gameplan_pad_event(side, previous[side], 0, 0, 0);
  }
}
static void sample(uint32_t side, uint32_t buttons, float x, float y) {
  buttons |= PES_GAMEPLAN_BUTTON_CONNECTED;
  uint32_t pressed = buttons & ~previous[side];
  pes_controller_custom_prematch_gameplan_pad_event(side, buttons, previous[side], x, y);
  previous[side] = buttons;
  uint32_t action = 0;
  if (pressed & PES_GAMEPLAN_BUTTON_B) action = PES_PAUSE_INPUT_BACK;
  else if (pressed & PES_GAMEPLAN_BUTTON_Y) action = PES_PAUSE_INPUT_ROLE;
  else if (pressed & PES_GAMEPLAN_BUTTON_A) action = PES_PAUSE_INPUT_DECIDE;
  else if (pressed & PES_GAMEPLAN_BUTTON_UP) action = PES_PAUSE_INPUT_UP;
  else if (pressed & PES_GAMEPLAN_BUTTON_DOWN) action = PES_PAUSE_INPUT_DOWN;
  else if (pressed & PES_GAMEPLAN_BUTTON_LEFT) action = PES_PAUSE_INPUT_LEFT;
  else if (pressed & PES_GAMEPLAN_BUTTON_RIGHT) action = PES_PAUSE_INPUT_RIGHT;
  pes_controller_custom_prematch_gameplan_input(side, action);
}
static void tick(uint32_t ms) {
  mock_now += (uint64_t)ms * 1000000;
  exhibition_gameplan_process_pending();
}
static void tap(uint32_t side, uint32_t button) {
  sample(side, button, 0, 0); tick(16);
  sample(side, 0, 0, 0); tick(16);
}
static void begin_drag(uint32_t side) {
  sample(side, PES_GAMEPLAN_BUTTON_A, 0, 0); tick(16); tick(240);
  assert(exhibition_gameplan_sides[side].position_dragging == 1);
}
static void test_tap(void) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[0];
  s->field_focus = 1;
  tap(0, PES_GAMEPLAN_BUTTON_A);
  assert(s->selected_area == PES_PREMATCH_GAMEPLAN_AREA_FIELD);
  assert(s->selected_index == 1 && s->field_focus == 1 && s->substitute_area == 0);
  uint8_t pos1[2], pos2[2];
  memcpy(pos1, mock_position(&mock_squads[0].formation[0], 1, 0), 2);
  memcpy(pos2, mock_position(&mock_squads[0].formation[0], 2, 0), 2);
  const uint32_t role1 = s->players[1].role, role2 = s->players[2].role;
  tap(0, PES_GAMEPLAN_BUTTON_LEFT);
  assert(s->field_focus == 2 && s->selected_index == 1);
  tap(0, PES_GAMEPLAN_BUTTON_A);
  assert(s->selected_area == PREMATCH_GAMEPLAN_NO_SELECTION);
  assert(s->players[1].role == role2 && s->players[2].role == role1);
  assert(memcmp(pos2, mock_position(&mock_squads[0].formation[0], 1, 0), 2) == 0);
  assert(memcmp(pos1, mock_position(&mock_squads[0].formation[0], 2, 0), 2) == 0);
  assert(mock_squads[0].saved == 1 && mock_squads[1].saved == 0 && mock_bench_swaps == 0);
  tap(0, PES_GAMEPLAN_BUTTON_A); tap(0, PES_GAMEPLAN_BUTTON_A);
  assert(s->selected_area == PREMATCH_GAMEPLAN_NO_SELECTION);
  tap(0, PES_GAMEPLAN_BUTTON_A);
  s->substitute_area = PES_PREMATCH_GAMEPLAN_AREA_BENCH;
  tap(0, PES_GAMEPLAN_BUTTON_A);
  assert(mock_bench_swaps == 1);
}
static void test_drag(void) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[1];
  s->field_focus = 5;
  uint8_t old[2];
  memcpy(old, mock_position(&mock_squads[1].formation[0], 5, 0), 2);
  TmpdbFormationValue other = mock_squads[1].formation[1];
  begin_drag(1);
  for (int i = 0; i < 60; i++) { sample(1, PES_GAMEPLAN_BUTTON_A, 1, -1); tick(16); }
  const uint8_t *pos = mock_position(&mock_squads[1].formation[0], 5, 0);
  assert(pos[0] > old[0] && pos[1] > old[1]);
  assert(s->field_focus == 5 && s->substitute_area == PES_PREMATCH_GAMEPLAN_AREA_FIELD);
  assert(s->selected_area == PREMATCH_GAMEPLAN_NO_SELECTION);
  sample(1, 0, 0, 0); tick(16);
  assert(!s->position_dragging && mock_squads[1].saved == 1 && mock_squads[0].saved == 0);
  assert(memcmp(&other, &mock_squads[1].formation[1], sizeof(other)) == 0);
  uint8_t saved_x = s->players[5].pitch_x;
  prematch_gameplan_refresh_side(1);
  assert(s->players[5].pitch_x == saved_x);
  begin_drag(1); sample(1, PES_GAMEPLAN_BUTTON_A, -1, 0); tick(32);
  pes_controller_custom_prematch_gameplan_pad_event(1, 0, previous[1], 0, 0); tick(16);
  assert(!s->position_dragging && mock_squads[1].saved == 2);
}
static void test_dpad(void) {
  for (uint32_t side = 0; side < 2; side++) {
    exhibition_gameplan_sides[side].field_focus = 5;
    begin_drag(side);
    const uint32_t dt = side ? 32 : 16;
    for (uint32_t i = 0; i < 960 / dt; i++) {
      sample(side, PES_GAMEPLAN_BUTTON_A | PES_GAMEPLAN_BUTTON_LEFT |
             PES_GAMEPLAN_BUTTON_DOWN, 0, 0); tick(dt);
    }
    sample(side, 0, 0, 0); tick(16);
  }
  assert(memcmp(mock_position(&mock_squads[0].formation[0], 5, 0),
                mock_position(&mock_squads[1].formation[0], 5, 0), 2) == 0);
  begin_drag(0);
  for (int i = 0; i < 200; i++) {
    sample(0, PES_GAMEPLAN_BUTTON_A | PES_GAMEPLAN_BUTTON_LEFT |
           PES_GAMEPLAN_BUTTON_DOWN, 0, 0); tick(32);
  }
  const uint8_t *pos = mock_position(&mock_squads[0].formation[0], 5, 0);
  assert(pos[0] == 0 && pos[1] == 0);
}
static void test_edges(void) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[0];
  s->page = PES_PREMATCH_GAMEPLAN_PAGE_ROOT;
  sample(0, PES_GAMEPLAN_BUTTON_A, 0, 0); tick(16); tick(300);
  sample(0, 0, 0, 0); tick(16);
  assert(s->page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE && !s->position_dragging);
  assert(s->selected_area == PREMATCH_GAMEPLAN_NO_SELECTION);
  sample(0, PES_GAMEPLAN_BUTTON_A, 0, 0);
  sample(0, PES_GAMEPLAN_BUTTON_A, 0, 0);
  sample(0, 0, 0, 0);
  sample(0, 0, 0, 0); tick(16);
  assert(s->selected_area == PES_PREMATCH_GAMEPLAN_AREA_FIELD);
  tick(16); tick(16);
  assert(s->selected_area == PES_PREMATCH_GAMEPLAN_AREA_FIELD);
  begin_drag(0);
  sample(0, PES_GAMEPLAN_BUTTON_A | PES_GAMEPLAN_BUTTON_B, 0, 0); tick(16);
  sample(0, 0, 0, 0); tick(16);
  assert(!s->position_dragging && s->page == PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE);
  assert(s->selected_area == PREMATCH_GAMEPLAN_NO_SELECTION);
}
static void test_role(void) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[0];
  s->field_focus = 3;
  const uint32_t old = s->players[3].role;
  uint8_t pos[2]; memcpy(pos, mock_position(&mock_squads[0].formation[0], 3, 0), 2);
  tap(0, PES_GAMEPLAN_BUTTON_Y);
  assert(s->players[3].role != old);
  assert(memcmp(pos, mock_position(&mock_squads[0].formation[0], 3, 0), 2) == 0);
  s->substitute_area = PES_PREMATCH_GAMEPLAN_AREA_BENCH;
  uint32_t saved = mock_squads[0].saved;
  tap(0, PES_GAMEPLAN_BUTTON_Y); assert(mock_squads[0].saved == saved);
  s->substitute_area = PES_PREMATCH_GAMEPLAN_AREA_FIELD;
  s->field_focus = 0; tap(0, PES_GAMEPLAN_BUTTON_Y);
  assert(s->players[0].role == 0 && mock_squads[0].saved == saved);
}
static void test_presets(void) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[0];
  static const uint32_t defenders[] = {4,4,4,4,4,4,3,3,5,5};
  static const uint32_t forwards[] = {3,1,2,1,2,2,2,3,2,1};
  for (uint32_t p = 0; p < PREMATCH_FORMATION_PRESET_COUNT; p++) {
    s->formation_preset = p; prematch_gameplan_apply_preset(0);
    assert(s->formation_preset == p);
    assert(strcmp(s->formation_label, prematch_formation_presets[p].label) == 0);
    uint32_t gk = 0, df = 0, fw = 0;
    for (uint32_t i = 0; i < 11; i++) {
      uint32_t role = s->players[i].role;
      gk += role == 0; df += role >= 1 && role <= 3; fw += role >= 9;
      for (uint32_t j = i + 1; j < 11; j++)
        assert(s->players[i].pitch_x != s->players[j].pitch_x ||
               s->players[i].pitch_y != s->players[j].pitch_y);
    }
    assert(gk == 1 && s->players[0].role == 0 && df == defenders[p] && fw == forwards[p]);
    s->formation_focus = 1;
    prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_RIGHT);
    assert(s->formation_preset == (p + 1) % PREMATCH_FORMATION_PRESET_COUNT);
  }
  s->formation_preset = PREMATCH_FORMATION_PRESET_COUNT;
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_RIGHT);
  assert(s->formation_preset == 0);
  uint32_t before = mock_squads[0].saved;
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DECIDE);
  assert(s->formation_picker_open && mock_squads[0].saved == before);
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DOWN);
  assert(s->formation_picker_focus == 1 && s->formation_preset == 0);
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_BACK);
  assert(!s->formation_picker_open && mock_squads[0].saved == before);
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DECIDE);
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DOWN);
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DECIDE);
  assert(!s->formation_picker_open && s->formation_preset == 1);
  assert(mock_squads[0].saved == before + 1);
}
static void test_profiles(void) {
  const u64 selects[3] = {HidNpadButton_A, HidNpadButton_Down, HidNpadButton_X};
  const u64 roles[3] = {HidNpadButton_Y, HidNpadButton_Up, HidNpadButton_B};
  const u64 backs[3] = {HidNpadButton_B, HidNpadButton_Left, HidNpadButton_A};
  for (int profile = 0; profile < 3; profile++) {
    assert(controller_profile_map_buttons(selects[profile], profile) == HidNpadButton_A);
    assert(controller_profile_map_buttons(roles[profile], profile) == HidNpadButton_Y);
    assert(controller_profile_map_buttons(backs[profile], profile) == HidNpadButton_B);
    HidAnalogStickState ls = {0}, rs = {0};
    int have_ls = 1, have_rs = 1;
    if (profile == 0) ls.x = JOYSTICK_MAX;
    if (profile == 1) ls.y = -JOYSTICK_MAX;
    if (profile == 2) rs.y = JOYSTICK_MAX;
    controller_profile_map_stick(profile, &ls, &have_ls, &rs, &have_rs);
    float x, y; normalize_stick(&ls, have_ls, &x, &y);
    assert(x > 0.99f && fabsf(y) < 0.001f);
    const u64 menu = controller_profile_menu_buttons(selects[profile], profile, &ls, have_ls);
    assert(menu == (HidNpadButton_A | HidNpadButton_Right));
    PrematchGameplanSide *s = &exhibition_gameplan_sides[profile % 2];
    const uint32_t side = (uint32_t)profile % 2;
    s->field_focus = 5;
    uint8_t before = s->players[5].pitch_x;
    sample(side, PES_GAMEPLAN_BUTTON_A, x, y); tick(16); tick(240);
    for (int i = 0; i < 6; i++) { sample(side, PES_GAMEPLAN_BUTTON_A, x, y); tick(32); }
    sample(side, 0, 0, 0); tick(16);
    assert(s->players[5].pitch_x > before && !s->position_dragging);
  }
}
static void assert_glyph_geometry(const GLfloat *v, int count, float height, int clipped) {
  const float expected_slope = ((EFOOTBALL_FONT_CELL_W - 1.0f) / EFOOTBALL_FONT_ATLAS_W) /
      (height * EFOOTBALL_FONT_CELL_W / EFOOTBALL_FONT_CELL_H * 2.0f / screen_width);
  for (int i = 0; i < count; i++) {
    const GLfloat *q = v + i * 24;
    assert(fabsf((q[1] - q[9]) * screen_height / 2.0f - height) < 0.001f);
    assert(q[4] > q[0] && q[6] > q[2]);
    assert(fabsf((q[6] - q[2]) / (q[4] - q[0]) - expected_slope) < 0.02f);
    const int cell0 = (int)(q[2] * EFOOTBALL_FONT_ATLAS_W / EFOOTBALL_FONT_CELL_W);
    const int cell1 = (int)(q[6] * EFOOTBALL_FONT_ATLAS_W / EFOOTBALL_FONT_CELL_W);
    assert(cell0 == cell1 && cell0 >= 0 && cell0 < EFOOTBALL_FONT_COUNT);
    if (clipped) {
      const float x0 = (q[0] + 1.0f) * screen_width / 2;
      const float x1 = (q[4] + 1.0f) * screen_width / 2;
      assert(x0 >= 159.99f && x1 <= 240.01f);
    }
  }
}
static void test_names(void) {
  const char *name = "Gianluigi Donnarumma";
  GLfloat start[2048], moving[2048];
  int n = emit_efootball_name_line("Messi", 5, 200, 100, 80, 15, 0, 0, start);
  assert(n == 5); assert_glyph_geometry(start, n, 15, 0);
  n = emit_efootball_name_line(name, (int)strlen(name), 200, 100, 80, 15, 0, 0, start);
  assert(n > 3 && n < 18); assert_glyph_geometry(start, n, 15, 0);
  const int dots = efootball_font_glyph_index('.');
  for (int i = n - 3; i < n; i++)
    assert((int)(start[i*24+2] * EFOOTBALL_FONT_ATLAS_W / EFOOTBALL_FONT_CELL_W) == dots);
  int a = emit_efootball_name_line(name, (int)strlen(name), 200, 100, 80, 15, 1, 1.2, start);
  int b = emit_efootball_name_line(name, (int)strlen(name), 200, 100, 80, 15, 1, 2.2, moving);
  assert(a != b || memcmp(start, moving, a * 24 * sizeof(GLfloat)) != 0);
  for (int ms = 0; ms < 10000; ms += 37) {
    n = emit_efootball_name_line(name, (int)strlen(name), 200, 100, 80, 15, 1, ms/1000.0, moving);
    assert(n > 0); assert_glyph_geometry(moving, n, 15, 1);
  }
  assert(gameplan_name_focus_seconds(0, 1, name) == 0.0);
  mock_now += 2000000000ULL;
  assert(gameplan_name_focus_seconds(0, 1, name) == 2.0);
  assert(gameplan_name_focus_seconds(1, 1, "Other") == 0.0);
  assert(gameplan_name_focus_seconds(0, 1, "Messi") == 0.0);
  assert(gameplan_name_focus_seconds(0, 0, "Messi") == 0.0);
}
static void test_zones(void) {
  // Every possible outfield role is normalized to the requested zone.
  for (uint32_t role = 1; role < 13; role++) {
    for (uint32_t cycle = 0; cycle < 2; cycle++) {
      uint32_t r = prematch_gameplan_zone_role(role, 52, 42, cycle);
      assert(r == 11 || r == 12);
      r = prematch_gameplan_zone_role(role, 52, 26, cycle);
      assert(r == 4 || r == 5 || r == 8);
      assert(prematch_gameplan_zone_role(role, 52, 12, cycle) == 1);
      r = prematch_gameplan_zone_role(role, 10, 12, cycle);
      assert(r == 1 || r == 2);
      r = prematch_gameplan_zone_role(role, 95, 42, cycle);
      assert(r == 10 || r == 11 || r == 12);
    }
  }
  assert(prematch_gameplan_zone_role(0, 52, 48, 1) == 0);
  assert(prematch_gameplan_zone_role(8, 52, 35, 0) == 8);
  assert(prematch_gameplan_zone_role(8, 52, 36, 0) == 11);
  assert(prematch_gameplan_zone_role(11, 52, 36, 1) == 12);
  assert(prematch_gameplan_zone_role(12, 52, 36, 1) == 11);
  assert(prematch_gameplan_zone_role(8, 52, 17, 0) == 1);
  assert(prematch_gameplan_zone_role(1, 52, 18, 0) == 4);
  PrematchGameplanSide *s = &exhibition_gameplan_sides[0];
  // Drag a central AMF over the forward boundary; verify after release/refresh.
  s->field_focus = 5;
  const uint8_t amf[2] = {35,52};
  mock_set_position(&mock_squads[0].formation[0], 5, amf, 0);
  mock_set_role(&mock_squads[0].formation[0], 5, 8, 0);
  prematch_gameplan_refresh_side(0);
  begin_drag(0);
  for (int i=0; i<15; i++) { sample(0, PES_GAMEPLAN_BUTTON_A, 0, -1); tick(16); }
  sample(0, 0, 0, 0); tick(16);
  assert(s->players[5].role == 11 || s->players[5].role == 12);
  assert(strncmp(s->formation_label, "CUSTOM ", 7) == 0);
  TmpdbFormationValue opponent = mock_squads[1].formation[0];
  TmpdbFormationValue defensive = mock_squads[0].formation[1];
  s->formation_picker_open = 1;
  s->formation_picker_focus = PREMATCH_FORMATION_PRESET_COUNT;
  prematch_gameplan_process_formation(0, PES_PAUSE_INPUT_DECIDE);
  assert(!s->formation_picker_open && !s->custom_shape[0]);
  assert(memcmp(&mock_squads[0].formation[0], &s->default_formation[0], sizeof(TmpdbFormationValue)) == 0);
  assert(memcmp(&mock_squads[0].formation[1], &defensive, sizeof(defensive)) == 0);
  assert(memcmp(&mock_squads[1].formation[0], &opponent, sizeof(opponent)) == 0);
}
static void test_ratings(void) {
  assert(main_menu_2p_team_selector_grade_half_steps((70+68+65+1)/3) == 6);
  assert(main_menu_2p_team_selector_grade_half_steps((74+66+67+1)/3) == 6);
  assert(main_menu_2p_team_selector_grade_half_steps((64+64+63+1)/3) == 5);
  assert(main_menu_2p_team_selector_grade_half_steps((84+83+81+1)/3) == 9);
  for (uint32_t i=1; i<=100; i++) {
    uint32_t grade = main_menu_2p_team_selector_grade_half_steps(i);
    assert(grade >= main_menu_2p_team_selector_grade_half_steps(i-1));
    assert(grade >= 2 && grade <= 10);
  }
}
int main(int argc, char **argv) {
  assert(argc == 2); setup();
  if (!strcmp(argv[1], "tap")) test_tap();
  else if (!strcmp(argv[1], "drag")) test_drag();
  else if (!strcmp(argv[1], "dpad")) test_dpad();
  else if (!strcmp(argv[1], "edges")) test_edges();
  else if (!strcmp(argv[1], "role")) test_role();
  else if (!strcmp(argv[1], "presets")) test_presets();
  else if (!strcmp(argv[1], "profiles")) test_profiles();
  else if (!strcmp(argv[1], "names")) test_names();
  else if (!strcmp(argv[1], "ratings")) test_ratings();
  else if (!strcmp(argv[1], "zones")) test_zones();
  else return 1;
  return 0;
}
