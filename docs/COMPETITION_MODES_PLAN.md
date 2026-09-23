# FootballNX 26 — Competition Modes Plan

Status: design baseline; Cup implementation flow updated 2026-09-24
Branch: cupleague
Owner: Androswitch Project
Scope: Match menu, Cup, League, Master League, persistence, and local multiplayer

## 1. Tujuan dan keputusan utama

Target berikutnya adalah menambahkan tiga keluarga mode:

- Cup dengan bracket, pertandingan eliminasi, kompetisi predefined, dan FootballNX Cup custom.
- League dengan jadwal musim, klasemen, simulasi, dan statistik.
- Master League dengan karier manager, squad, transfer, kontrak, ekonomi, kalender, dan season rollover.

Ketiga mode tidak boleh dibuat sebagai tiga implementasi terpisah. Semuanya harus memakai:

1. satu Competition Core untuk fixture, jadwal, bracket, klasemen, dan hasil pertandingan;
2. satu Match Handoff untuk meneruskan fixture ke route pertandingan yang sudah stabil;
3. satu Save Core dengan schema version dan migration;
4. satu data identity layer yang tetap mengikuti BaseId sebagai identitas pemain utama;
5. satu controller/input layer yang dapat dipakai menu, pertandingan, dan multiplayer lokal.

Urutan pengerjaan yang direkomendasikan:

1. Frontend state dan Competition Core.
2. Cup MVP.
3. League MVP.
4. Local multiplayer Cup.
5. Master League vertical slice.
6. Ekspansi konten, promotion/relegation, create-a-club, youth, staff, dan continental competitions.

Alasan urutan ini adalah Cup menguji seluruh siklus dasar dengan state paling kecil. League kemudian menguji scheduler dan simulasi. Master League baru dimulai setelah persistence dan transfer identity benar-benar stabil.

## 2. Baseline repository saat ini

Branch cupleague berjalan di atas fondasi yang sudah ada:

- Exhibition sudah memiliki route title screen, main menu, team selection, match settings, Game Plan, pertandingan, result, dan kembali ke menu.
- Migration build memiliki sekitar 443 tim selectable dalam 33 kategori.
- Team catalog, badge atlas, kit data, roster, dan PESDB mapping sudah tersedia sebagai sumber data.
- Native MatchSetup dan setter match sudah digunakan untuk HOME/COM, match time, extra time, penalty, weather, season, turf, dan pitch condition.
- Native Game Plan dan hasil pertandingan sudah diuji melalui jalur Exhibition dan 2 Player lab.
- Controller support applet sudah dipakai untuk memastikan dua Npad slot ketika mode dua pemain dimulai.
- Custom overlay dan custom input sudah tersedia untuk menu, popup, Game Plan, pause, result, team selector, dan settings.
- Mode 2 Player saat ini belum menjadi sistem Cup/League multiplayer dengan banyak logical player.
- Scheduler musim, career state, dan transfer market belum ada. Cup bracket,
  handoff/result, dan tiga slot save Cup sudah diimplementasikan; perlu QA hardware
  untuk flow bracket editor dan resume lintas restart.

Perubahan pada mode kompetisi harus menjaga Exhibition sebagai regression baseline. Perubahan visual stadium atau roof camera yang tidak terkait tidak boleh dicampur ke milestone mode kompetisi.

## 3. Struktur menu utama baru

### 3.1 Empat tile utama

Main menu tetap menggunakan empat tile dengan logical order:

1. Match
2. Modes
3. Settings
4. Credits

Tile lama Exhibition diganti labelnya menjadi Match. Tile lama 2 Player diganti menjadi Modes. Settings dan Credits tetap menjadi tile mandiri.

Logical order harus dipisahkan dari native tile index. Runtime saat ini masih memiliki empat native choice dan mapping native-to-visual. Mapping tersebut dipertahankan sebagai adapter agar perubahan urutan visual tidak merusak handler native.

### 3.2 Match submenu

Ketika Match dipilih, halaman utama tidak berpindah ke flow lain. State menu berubah menjadi:

Title:

    Select Match Mode

Item:

1. Exhibition
2. 2 Player

Helper:

    [A] Select    [B] Back

Back pada halaman ini kembali ke empat tile utama tanpa masuk ke flow native lama.

Exhibition mempertahankan flow yang sudah stabil:

    Match > Exhibition > HOME/COM > Match Settings > Proceed > Game Plan > Play

2 Player mempertahankan validasi dua controller, kemudian membuka team selector dan prematch hub yang sudah ada.

### 3.3 Modes submenu

Ketika Modes dipilih, halaman berubah menjadi:

Title:

    Select Modes

Item:

1. Cup
2. League
3. Master League

Helper:

    [A] Select    [B] Back

Setiap mode mempunyai landing page yang konsisten:

    New
    Continue
    [B] Back

Cup menggunakan tiga slot save tetap. League dan Master League sebaiknya menggunakan framework slot yang sama, tetapi jumlah slot dapat diperluas pada tahap berikutnya.

### 3.4 Aturan Back dan helper sprite

Sprite B yang sudah tersedia dipakai sebagai helper Back pada semua submenu custom.

Hierarki Back:

- Select Match Mode > Main Menu.
- Select Modes > Main Menu.
- Cup landing > Select Modes.
- Cup save slots > Cup landing.
- Cup Settings > Cup landing.
- Cup bracket editor > lima tombol Cup Hub.
- Cup Hub > Top to Menu.
- Bracket setelah result > tetap di Cup Hub.
- League dan Master League mengikuti pola yang sama.

B tidak boleh meneruskan event ke native page di belakang custom page. Setiap custom state harus memakan input B sendiri dan hanya menutup state yang sedang aktif.

Confirmation untuk keluar dari Cup yang belum di-save adalah kandidat UX
lanjutan; implementasi Cup saat ini memakai `Save` eksplisit dan B langsung
kembali ke menu.
    [A] Yes    [B] No

## 4. State machine frontend

State machine yang direkomendasikan:

    MAIN_MENU
      -> SELECT_MATCH_MODE
      -> SELECT_MODES
      -> SETTINGS
      -> CREDITS

    SELECT_MATCH_MODE
      -> EXHIBITION
      -> TWO_PLAYER

    SELECT_MODES
      -> CUP_LANDING
      -> LEAGUE_LANDING
      -> MASTER_LEAGUE_LANDING

    CUP_LANDING
      -> CUP_SAVE_SLOTS
      -> CUP_SETTINGS
      -> SELECT_MODES

    CUP_SETTINGS
      -> CUP_SELECT_TEAMS
      -> CUP_HUB
      -> CUP_LANDING

    CUP_HUB
      -> CUP_FIXTURE_PREVIEW
      -> CUP_BRACKET_RESULT
      -> CUP_COMPLETE
      -> CUP_LANDING

Perpindahan state harus menggunakan satu fungsi transition dengan:

- current state;
- next state;
- source reason;
- active save slot;
- pending fixture;
- pending native flow;
- input owner;
- transition serial;
- timeout/failure fallback.

Transition serial mencegah input lama dari halaman sebelumnya mengaktifkan halaman baru.

## 5. Cup — spesifikasi hardened

### 5.1 Landing page

Halaman Cup pertama:

    Cup

    New
    Continue
    [B] Back

New membuka Cup Settings.

Continue membuka halaman tiga slot:

    Select Cup Save

    Slot 1
    Slot 2
    Slot 3
    [B] Back

Slot menampilkan:

- Nama Cup.
- Logo Cup.
- Tim pengguna.
- Ronde terakhir.
- Matchday atau ronde.
- Status In Progress atau Completed.
- Waktu terakhir disimpan.
- Build/content version.

Slot kosong disabled. Slot corrupt ditandai Corrupt dan tidak boleh diload. Slot berisi data harus meminta confirmation sebelum dipakai.

### 5.2 Cup Settings

Urutan field:

1. Select Cup.
2. Number of Player.
3. Number of Teams.
4. Home Away (ON/OFF).
5. 3rd Place Match (ON/OFF).
6. Next.

Kembali menggunakan helper B, bukan tile Back tambahan. Penalty selalu ON
karena setiap fixture Cup harus memiliki pemenang.

#### Select Cup

Daftar Cup mengambil referensi tampilan dari Football Life 26 dan PES21 PC yang tersedia secara lokal, termasuk logo yang memang sudah dipakai pada runtime pengguna.

Minimal daftar awal:

- Cup predefined dari liga/negara yang datanya eligible.
- Cup continental atau international yang data pesertanya lengkap.
- FootballNX Cup.

FootballNX Cup ditandai jelas sebagai:

    Custom Cup

Nama, logo, dan metadata official harus dipisahkan dari aturan kompetisinya. Jika aset resmi tidak dapat dipublikasikan, gunakan manifest logical ID dan project-authored fallback tanpa menyalin proprietary raw asset ke repository.

#### Number of Player

Field ini harus didefinisikan secara tegas sebagai jumlah logical human player slot, bukan jumlah controller fisik.

Contoh:

- 1 player = satu tim milik manusia.
- 2 player = dua tim milik manusia.
- 3 player = tiga logical owner yang masing-masing memilih tim.

Controller fisik v1 tetap dua. Dengan demikian, tiga player tidak berarti tiga orang dapat mengontrol pertandingan secara bersamaan. Saat fixture berjalan:

- Jika dua tim human bertemu, pad 1 dan pad 2 mengontrol kedua sisi.
- Jika hanya satu tim human bertanding, satu pad mengontrol tim tersebut dan sisi lain menjadi COM.
- Jika lebih dari dua logical human owner mengikuti kompetisi, mapping mereka ke pad dilakukan per fixture dan dapat berpindah.
- Jika ingin dua orang mengontrol satu tim, gunakan same-team co-op sebagai mode terpisah setelah local versus stabil.

Semua halaman setup Cup dimiliki oleh P1. P1 yang membuka New/Continue, mengubah
seluruh Match Settings, dan mengisi slot langsung di Cup Hub. P2 tidak
boleh menggeser fokus atau mengubah setting pada halaman-halaman tersebut. Saat
Cup Hub pertama kali dibuka, runtime menampilkan gate controller berdasarkan
`Number of Player`: nilai 1 memerlukan pad 1; nilai 2 atau lebih memerlukan pad
1 dan pad 2 yang benar-benar terdeteksi. Gate ini boleh membuka native Controller
Support applet, dan Cup Hub tetap menampilkan status `WAITING` sampai requirement
terpenuhi. Jumlah logical player di atas dua tetap menggunakan dua pad fisik dan
assignment per fixture, bukan menuntut controller ketiga.

Batas awal yang direkomendasikan adalah 1 sampai 8 logical player slot, dibatasi oleh jumlah tim Cup. Batas ini bukan batas engine; hanya batas UI dan complexity budget v1.

#### Number of Teams

Untuk FootballNX Cup custom:

- Minimum 3 tim.
- Maximum v1: 32 tim.
- Tim harus unique.
- Semua tim harus eligible untuk Cup.

Untuk predefined Cup, jumlah tim fixed berdasarkan format kompetisi. English
Cup memakai 16 slot eliminasi tanpa bye meskipun kategori Inggris dalam
katalog migrasi memiliki 19 klub eligible; klub di luar 16 slot awal tetap
dapat dipilih melalui selector untuk mengganti peserta. Saat manifest
kompetisi yang lebih lengkap tersedia, peserta awal diambil dari manifest
tersebut dengan validasi roster/kit.

#### General Setting di Cup Hub

COM Level hanya ditampilkan apabila:

    number_of_player != number_of_teams

Artinya masih terdapat tim yang tidak dimiliki logical human player.

Jika semua tim dimiliki player, field disembunyikan. Pengaturan lain memakai
komponen General Settings Exhibition yang sama dari Cup Hub: Match Time,
Overtime, Substitutions, Injuries, Ball, dan VAR. Penalties selalu ON.

#### Home Away

Label UI:

- Home Away ON = tie dua leg dengan aggregate score pada ronde sebelum final.
- Home Away OFF = satu pertandingan eliminasi pada tiap pairing.

Interpretasi internal:

- Semua Cup memakai format knockout.
- Final dan laga juara 3 adalah pertandingan tunggal.

Jika Home Away ON, pairing sebelum final memiliki leg 1 dan leg 2;
kelolosan ditentukan dari jumlah gol agregat.

Jika Home Away OFF, tim yang kalah langsung tersingkir. Jumlah tim yang bukan
power-of-two ditangani dengan bye atau preliminary round.

#### 3rd Place Match

Jika ON dan minimal empat tim, dua tim yang kalah di semifinal memainkan
perebutan juara 3. Fixture ini diprioritaskan sebelum final bila ada tim
player; COM vs COM baru disimulasikan setelah match player selesai.

#### Game Time

Gunakan pilihan waktu yang sama dengan Exhibition dan 2 Player. Jangan membuat enum waktu baru.

#### Extra Time, Penalty, dan Max Substitutions

Extra Time dapat ON/OFF. Penalty selalu ON dan tidak menjadi pilihan setting;
aturan ini harus terlihat pada Cup Hub. Max Substitutions memakai rentang yang
sama dengan General Setting (3-5) dan diteruskan ke MatchSetup native. Setiap
fixture Cup harus menghasilkan pemenang, termasuk jika Extra Time OFF.

### 5.3 Bracket editor menggantikan halaman Select Teams

Flow baru: `Cup > Cup Settings > Cup Hub`. Bagan pembuka tampil dengan semua
tim kosong tetapi setiap slot telah bertanda `P1`, `P2`, atau `COM`. Editor
bagan adalah bagian Cup Hub, bukan halaman Select Teams terpisah. Tombol
`Next` disabled sampai seluruh slot terisi tim unik dan valid.

P1 memilih `Bracket` untuk masuk edit mode. Fokus melintasi slot pembuka dari
atas ke bawah; A membuka selector tim satu sisi yang memakai carousel, atlas,
dan pengelompokan Exhibition/2 Player. Selector predefined Cup langsung
membuka kategori liga yang eligible; FootballNX Cup membuka daftar kategori.
B mengembalikan fokus ke lima tombol Hub.

X mengisi hanya slot kosong babak pembuka secara acak, tanpa mengganti pilihan
manual. Ronde lanjutan dan Champion tetap TBD sampai hasil fixture sebelumnya
diproses; bye pembuka pun tidak mengisi slot ronde lanjutan lebih awal.
Y memilih slot asal, lalu Y pada slot tujuan menukar tim sekaligus owner
P1/P2/COM; menekan Y lagi pada slot asal membatalkan swap. Memilih tim yang
sudah terpasang lewat A juga menukar tim kedua slot tanpa duplikasi. Tidak
ada simulasi pertandingan selama tahap pengisian atau pertukaran bagan.
Setelah pertandingan pertama dimulai, `Bracket` disabled dan semua assignment
terkunci. Maksimum delapan logical player tetap dikontrol lewat dua controller
fisik; P1 mengurus seluruh setup.

### 5.4 Full-page Cup Hub dan bracket

Setelah setup selesai, masuk ke full-page custom Cup Hub.

Hub wajib menampilkan:

- Logo dan nama Cup.
- Format.
- Ronde aktif.
- Jumlah tim.
- Tim pengguna.
- Bracket lengkap.
- Highlight fixture berikutnya.
- Rule Extra Time/Penalty.
- Slot save aktif.
- Status player/controller assignment jika fixture berikutnya melibatkan human team.

Bagan memakai slot ringkas `[crest] MUN - P1/COM` dengan skor pertandingan.
Tim yang mendapat bye hanya memakai satu slot; fixture ronde mendatang yang
belum terisi menampilkan dua slot TBD. Untuk Cup 3–4 tim, Semi Final,
Final, dan Champion muat dalam satu panel dengan konektor pendek. Setiap
halaman vertikal menampilkan maksimal dua fixture/empat tim babak aktif,
dengan crest dan pelat skor berukuran lebih besar. Cup 16 tim mempunyai
empat halaman vertikal pada Round of 16 dan dua pada Quarter Final.
L/R (SL/SR pada Joy-Con horizontal) berpindah antar-stage secara horizontal,
sedangkan Y pada fokus tombol Hub mengganti halaman vertikal di stage aktif.
Ikon shoulder berada di kedua pojok header bagan dan tersembunyi saat editor
bagan aktif; pada editor, Y tetap untuk Swap. Kiri/kanan memindahkan fokus
antartombol. Match Schedule menampilkan maksimal empat fixture relevan pada
halaman bagan aktif dan ronde lanjutannya, termasuk TBD untuk lawan yang
belum diketahui; hasil selesai memakai crest, kode tiga huruf, dan skor.
Tombol berada di luar container utama dengan jarak yang jelas.

Urutan tombol: `Bracket`, `Next`, `General Setting`, `Save`, `Top to Menu`. `Bracket` hanya aktif
sebelum match pertama. `Next` baru aktif jika seluruh tim ter-assign; setelah
Cup selesai tombol ini hilang dan fokus otomatis pindah ke `Top to Menu`.
`Save` membuka tiga slot persistent yang bisa dilanjutkan dari `Continue`.

Helper B tetap dapat ditampilkan sebagai shortcut Back to Menu, tetapi tidak dihitung sebagai tombol konten ketiga.

`General Setting` memakai layout dan kontrol Exhibition. Nilainya dapat
diubah dari Cup Hub lalu diteruskan ke match berikutnya; aturan turnamen
(Home Away dan 3rd Place Match) tetap berasal dari Cup Settings.

### 5.5 Next dan match handoff

Saat Next dipilih:

1. Ambil fixture berikutnya.
2. Resolve COM/human assignment.
3. Resolve home/away.
4. Build CurrentMatchContext.
5. Apply native match settings.
6. Set HOME/AWAY team dan pad port.
7. Masuk ke Game Plan atau fixture preview sesuai mode.
8. Mulai route pertandingan yang sudah dipakai Exhibition.

CurrentMatchContext minimal:

    competition_id
    cup_id
    round_id
    fixture_id
    home_team_id
    away_team_id
    logical_player_owner_home
    logical_player_owner_away
    pad_owner_home
    pad_owner_away
    match_mode
    game_time
    extra_time
    penalty
    venue
    seed

### 5.6 After match dan bracket result

Setelah pertandingan:

1. Baca score native.
2. Baca extra time dan penalty result.
3. Tulis MatchResult.
4. Update fixture.
5. Update bracket atau aggregate score.
6. Simpan slot.
7. Kembali ke Cup Bracket Result.

Implementasi awal membaca skor reguler/extra time dari cache native saat
halaman final ditutup melalui `Back to Cup`, lalu memperbarui fixture dan
mensimulasikan laga COM yang tersisa. Pembacaan pemenang adu penalti native
masih perlu diverifikasi di hardware; skor imbang belum cukup untuk menentukan
pemenang PK secara otoritatif.

Halaman result menampilkan:

- Score.
- Pemenang.
- Tim yang tersingkir.
- Ronde.
- Bracket yang telah diperbarui.
- Fixture berikutnya.
- Tombol Next.
- Tombol Back to Menu.

Jika fixture berikutnya adalah COM vs COM, pertandingan dapat disimulasikan otomatis. Jika fixture memiliki human team, player diberi opsi Play atau Simulate sesuai aturan mode.

### 5.7 Single-player knockout auto-simulation

Jika Cup hanya mempunyai satu logical player dan formatnya Knockout:

- Jika tim player masih lolos, player dapat melanjutkan seperti biasa.
- Jika seluruh sisa fixture tidak melibatkan tim player, semua pertandingan tersisa disimulasikan otomatis.
- Jika tim player tersingkir, bracket tetap dilanjutkan melalui simulation.
- Setelah champion ditentukan, tampilkan Game Over dengan status:

      Champion: <team>
      Your team: Eliminated

- Jika player menjadi juara, tampilkan Cup Complete dan trophy presentation.

Simulasi harus menampilkan progress singkat agar tidak terlihat hang atau crash:

    Simulating Quarter Final...
    Simulating Semi Final...
    Simulating Final...

User harus dapat skip animasi simulasi, tetapi hasil tetap dihitung melalui deterministic simulator.

### 5.8 Cup completion

Halaman selesai memiliki:

- Cup logo.
- Winner badge.
- Winner name.
- Runner-up.
- Final score.
- Player result.
- Bracket lengkap.
- Season/Cup history entry.
- Save as Completed.
- Back to Menu.

Completed slot tidak boleh hilang saat memilih New. New harus meminta slot target dan confirmation overwrite.

## 6. League plan

League memakai landing page dan save flow yang sama, tetapi tidak memakai bracket.

Minimum League MVP:

- satu liga 20 tim;
- double round robin;
- 38 matchday;
- Play atau Quick Sim;
- klasemen;
- fixture list;
- hasil;
- top scorer sederhana;
- save/load di tengah musim;
- season completion.

League definition harus data-driven:

    competition_id
    display_name
    country
    team_count
    participant_team_ids
    rounds
    home_away
    points_win
    points_draw
    points_loss
    tie_breakers
    promotion_group
    relegation_group

Category di Exhibition tidak otomatis menjadi League definition. Participant list harus disaring melalui eligibility manifest agar tim dengan roster/kit/data tidak lengkap tidak masuk secara tidak sengaja.

Tie-breaker awal:

1. Points.
2. Goal difference.
3. Goals scored.
4. Head-to-head jika data tersedia.
5. Deterministic fallback jika masih seri.

Schedule generator harus memastikan:

- setiap pasangan bertemu jumlah yang benar;
- home/away seimbang;
- tidak ada fixture duplicate;
- fixture dapat direbuild dari seed;
- round number dan tanggal konsisten setelah load.

League Hub:

    Calendar
    Table
    Fixtures
    Results
    Team Stats
    Player Stats
    Save
    Back to Menu

Feature lanjutan:

- promotion/relegation;
- playoff promosi;
- domestic cup qualification;
- continental qualification;
- multiple divisions;
- derby/rivalry;
- postponed fixture;
- international break;
- season awards;
- season history.

## 7. Master League plan

Master League dibangun di atas League dan Cup, bukan implementasi pertandingan baru.

### 7.1 Start type

MVP:

- Existing Club Career.

Ekspansi:

- Create-a-Club.

Existing Club Career mengambil squad, badge, kit, league, budget, reputation, dan board target dari data team catalog.

Create-a-Club tahap awal menggunakan:

- nama;
- singkatan;
- warna;
- badge template;
- kit template;
- liga;
- budget awal;
- squad awal;
- reputation.

Editor badge dan kit penuh baru dibuat setelah save/career core stabil.

### 7.2 Career dashboard

Master League Hub:

    Inbox
    Calendar
    Squad
    Game Plan
    Transfers
    Scouting
    Finances
    Standings
    Board Objectives
    Save
    Back to Menu

### 7.3 Squad dan player state

Player state minimal:

    base_id
    native_pes21_id
    current_team_id
    position
    overall
    form
    fitness
    morale
    injury_status
    suspension_status
    contract_end
    wage
    transfer_status

Transfer hanya mengubah current_team_id dan contract state. Jangan membuat salinan pemain untuk setiap klub.

### 7.4 Transfer MVP

- transfer window;
- transfer budget;
- wage budget;
- buy;
- sell;
- free agent;
- loan sederhana;
- contract length;
- wage negotiation;
- transfer list;
- squad registration.

Ekspansi:

- scouting;
- shortlist;
- valuation;
- release clause;
- signing bonus;
- agent fee;
- loan-to-buy;
- youth academy;
- rival bids.

PESDB identity wajib mengikuti BaseId sebagai master identity dan persistent BaseId-to-NativePES21Id mapping. Reused numeric ID saja tidak cukup untuk membawa face, commentary, atau asset lama.

### 7.5 Calendar dan simulation

Event Master League:

    LEAGUE_MATCH
    DOMESTIC_CUP
    CONTINENTAL_MATCH
    TRAINING
    REST
    TRANSFER_WINDOW_OPEN
    TRANSFER_WINDOW_CLOSE
    INTERNATIONAL_BREAK
    BOARD_MEETING
    CONTRACT_RENEWAL
    SEASON_END

Setiap match menawarkan Play atau Simulate. Simulator harus menggunakan team strength, home advantage, form, fatigue, morale, player availability, dan deterministic seed.

### 7.6 Finance dan board

MVP:

- transfer budget;
- wage budget;
- weekly wage;
- prize money;
- match income;
- simple board objective;
- board confidence: Safe, Warning, Fire.

Ekspansi:

- sponsor;
- staff cost;
- stadium income;
- attendance;
- fan satisfaction;
- facilities.

### 7.7 Master League vertical slice

Vertical slice pertama dianggap sukses jika user dapat:

1. memilih existing club;
2. memainkan atau mensimulasikan satu liga penuh;
3. mengikuti satu domestic cup;
4. membeli dan menjual pemain;
5. mengatur contract/wage dasar;
6. mengelola squad;
7. menyimpan dan melanjutkan di tengah musim;
8. menyelesaikan musim;
9. masuk ke season berikutnya.

Youth, staff, sponsor kompleks, continental tournament, dan full create-a-club editor ditunda sampai slice ini stabil.

## 8. Native reuse versus custom full page

### 8.1 Native yang sebaiknya dipakai

Kode native yang sudah terbukti dan layak digunakan:

- Native four-tile page dan choice nodes untuk shell main menu.
- Native focus/touch integration melalui main menu selected entry.
- Native controller support applet untuk dua physical controller slots.
- Native Exhibition team/match plan setup.
- Native MatchSetup dan tmpdb match setters.
- Native HOME/AWAY pad port assignment.
- Native Game Plan.
- Native gameplay.
- Native match result dan pause route.
- Native uniform, stadium, dan match-settings hooks yang sudah dipakai oleh Exhibition.
- Native flow handoff ke TutorialMatch/MatchSetup yang sudah terbukti.

Symbol/function family yang menjadi kandidat reuse:

- main_menu_choice_set_active;
- main_menu_graphics_create;
- pes_main_menu_simplify;
- pes_main_menu_selected_entry;
- pes_main_menu_pad_event;
- exhibition_flow_direct_set;
- exhibition_matchplan_setup_team;
- exhibition_matchplan_set_pad_port;
- exhibition_matchplan_setup_tmpdb;
- exhibition_match_set_match_time;
- exhibition_match_set_ex;
- exhibition_match_set_pk;
- existing team catalog and roster lookup.

Nama dan offset native tetap harus divalidasi melalui build target. Dokumen ini tidak menganggap semua symbol otomatis aman untuk dipanggil dari state baru.

### 8.2 Custom yang lebih aman

Custom full page dipakai untuk:

- Select Match Mode.
- Select Modes.
- Cup landing.
- tiga save slot.
- Cup Settings.
- Number of Player sebagai baris Cup Settings.
- Bracket editor dengan logical player slot.
- full bracket.
- Cup Hub.
- Cup result/completion.
- League calendar/table.
- Master League dashboard.
- transfer market.
- career save/load.

Native Cup/League/Master League screen, scheduler, dan career save belum memiliki bukti stabil di branch ini. Jangan memaksa membuka flow native yang belum di-audit hanya demi mendapatkan tampilan PC. Custom page lebih aman, deterministic, dan dapat menutup semua state sendiri.

### 8.3 Strategi hybrid

Pola implementasi:

    Custom frontend state
      -> native data lookup
      -> native MatchSetup/Game Plan
      -> native gameplay
      -> native result read
      -> custom bracket/table/career update

Dengan pola ini, custom page hanya mengatur kompetisi, sedangkan bagian paling sensitif seperti squad, uniform, gameplay, dan result tetap memakai route native yang sudah lolos uji.

## 9. Data dan file layout

Usulan file project-authored:

    data/competitions/cups/catalog.json
    data/competitions/cups/footballnx_cup.json
    data/competitions/leagues/catalog.json
    data/competitions/leagues/english.json
    data/competitions/leagues/spanish.json
    data/competitions/eligibility.json
    data/competitions/content_manifest.json
    data/master_league/rules.json
    data/master_league/board_objectives.json

Runtime-generated data:

    local SaveData/competition_slot_1
    local SaveData/competition_slot_2
    local SaveData/competition_slot_3

Save runtime tidak boleh di-commit. Raw APK, OBB, CPK, PAK, extracted game libraries, private keys, dan raw decompiler output tetap berada di local-inputs atau local-debug sesuai policy repository.

Competition manifest harus memiliki:

- stable competition ID;
- display name;
- logo logical ID;
- participant source;
- participant eligibility;
- format;
- rule set;
- content version;
- fallback behavior.

## 10. Save schema dan recovery

Setiap save memiliki:

    schema_version
    build_id
    content_manifest_version
    save_slot_id
    mode
    status
    created_at
    updated_at
    checksum
    state

Cup state menyimpan:

- Cup config;
- deterministic seed;
- participants;
- logical player owners;
- controller assignment policy;
- bracket;
- fixtures;
- results;
- current fixture;
- current round;
- status;
- history.

League state menyimpan:

- competition config;
- seed;
- participants;
- schedule;
- fixtures;
- results;
- standings;
- current matchday;
- statistics;
- season history.

Master League state menyimpan semua bagian League/Cup ditambah:

- manager;
- club;
- player assignment;
- contracts;
- finances;
- transfer market;
- morale/form/fatigue;
- board objectives;
- season progression.

Write policy:

1. Tulis ke temporary file.
2. Flush dan validasi size/checksum.
3. Rename atomically menjadi slot aktif.
4. Simpan backup slot terakhir.
5. Saat load, validasi schema, checksum, build compatibility, dan content manifest.

Jika validasi gagal, jangan mencoba menjalankan fixture. Tampilkan Corrupt Save dan pertahankan backup.

## 11. Milestone implementasi

### M0 — Frontend state foundation

- Logical four-tile menu.
- Match submenu.
- Modes submenu.
- B helper.
- State transition guard.
- No native input fall-through.

Exit criteria: user dapat membuka Match dan Modes, masuk/keluar submenu, dan Exhibition tetap berjalan seperti sebelumnya.

### M1 — Competition Core

- CompetitionDefinition.
- TeamRef.
- Fixture.
- MatchResult.
- deterministic seed.
- MatchContext.
- save schema awal.
- unit tests.

Exit criteria: fixture dummy dapat dibuat, disimpan, diload, dan diteruskan ke native match route.

### M2 — Cup MVP

- FootballNX Cup custom.
- 8 tim.
- knockout satu leg.
- extra time/penalty.
- Bracket editor multi-player.
- full bracket.
- three save slots.
- after-match update.
- auto-sim remainder.

Exit criteria: satu Cup dapat diselesaikan dari New sampai Game Over tanpa restart manual.

### M3 — Cup expansion

- predefined Cup catalog;
- 16/32 tim;
- Home Away;
- seeded draw;
- preliminary round;
- local versus;
- result presentation.

### M4 — League MVP

- satu liga 20 tim;
- 38 matchday;
- table;
- fixture list;
- quick simulation;
- season completion;
- save/load.

### M5 — Local multiplayer

- dua controller;
- local versus;
- logical player ownership;
- deterministic controller assignment;
- same-team co-op setelah versus stabil.

### M6 — Master League vertical slice

- existing club;
- satu League;
- satu Cup;
- transfer window;
- contract/wage;
- board target;
- season rollover.

### M7 — Content expansion dan polish

- seluruh league definition yang eligible;
- Cup tambahan;
- promotion/relegation;
- create-a-club;
- scouting/youth/staff;
- continental competitions;
- long-run hardware QA.

Setiap milestone harus dibuild dengan command full-loose terbaru yang sudah lolos validation. Bare build tidak boleh menjadi satu-satunya build gate.

## 12. Testing matrix

### Unit tests

- Schedule uniqueness.
- Home/away balance.
- Standings.
- Tie-breaker.
- Bracket/bye.
- Aggregate score.
- Extra time/penalty policy.
- Deterministic simulation.
- Save checksum.
- Schema migration.
- BaseId identity.
- Transfer budget.
- Logical player assignment.

### Integration tests

- Main Menu > Match > Exhibition.
- Main Menu > Match > 2 Player.
- Main Menu > Modes > Cup.
- Cup Settings > Bracket kosong > assign/random/swap > Next.
- Bracket > MatchContext > Game Plan.
- Result > Bracket update.
- Continue > three save slots > resume.
- League fixture > play/sim > table.
- Master League transfer > match > season rollover.

### Edge cases

- 3-team Cup.
- Number of players greater than two.
- Number of players equal to number of teams.
- No human team in current fixture.
- Human versus human fixture.
- Duplicate team selection.
- Non-power-of-two knockout.
- Draw with both extra time and penalty disabled.
- Player eliminated before final.
- COM versus COM remaining bracket.
- Corrupt save.
- Content manifest changed between builds.
- Controller disconnected before kickoff.

### Hardware

- cold boot;
- suspend/resume;
- three save slots;
- long Cup;
- 38-match League;
- multiple Master League seasons;
- two-controller pairing;
- controller disconnect/reconnect;
- pause/replay/penalty;
- memory pressure;
- frame pacing;
- no regression pada Exhibition.

Catatan regresi aset menu (2026-09-24): PNG ornamen header Cup berukuran
2172×724, melewati batas lama 2048 pada satu sumbu walaupun jumlah pikselnya
lebih kecil dari 2048². Kegagalan decode itu membuat seluruh batch tekstur
menu di-decode dan di-upload lagi setiap frame, sehingga tile menu hingga Cup
melambat dan ornamen tampil hitam. Decoder kini membatasi dimensi 4096 serta
total piksel 2048²; upload batch dicoba sekali per GL context, dan ornamen
tidak digambar bila upload gagal. FPS hardware tetap perlu diverifikasi.

## 13. Definition of Done

### Cup

- New, Continue, dan tiga slot berjalan.
- Semua setting tervalidasi.
- 3+ custom teams didukung.
- Player assignment terdokumentasi.
- Bracket tidak rusak setelah load.
- Match result kembali ke bracket.
- Sisa pertandingan dapat disimulasikan.
- Winner/Game Over ditampilkan.

### League

- Schedule valid.
- Table valid.
- Play dan simulate bekerja.
- Mid-season save/load bekerja.
- Season completion bekerja.

### Master League

- Existing club dapat dimulai.
- Squad dapat dikelola.
- Transfer dan contract berjalan.
- Budget dan board state berubah.
- Calendar dan fixture berjalan.
- Save/load dan season rollover berjalan.

## 14. Rekomendasi implementasi pertama

Pekerjaan pertama pada branch cupleague sebaiknya bukan langsung membuat seluruh daftar Cup PC. Mulai dari vertical slice yang dapat diuji:

1. Ubah main menu menjadi Match, Modes, Settings, Credits.
2. Tambahkan Select Match Mode dan Select Modes sebagai custom state.
3. Tambahkan Cup landing dengan New, Continue, dan Back.
4. Implementasikan Cup Settings.
5. Implementasikan assignment langsung di bracket untuk minimal tiga logical
   player slot dengan dua physical controller.
6. Buat FootballNX Cup knockout 8 tim.
7. Bangun full bracket custom.
8. Handoff satu fixture ke native MatchSetup/Game Plan/gameplay.
9. Baca hasil dan update bracket.
10. Save ke satu dari tiga slot.
11. Setelah loop ini stabil, aktifkan slot kedua/ketiga, auto-simulation, dan predefined Cup.

Keputusan desain yang paling penting adalah memisahkan:

- logical player;
- physical controller;
- team participant;
- current fixture;
- native match side.

Jika pemisahan ini benar sejak awal, Cup dengan tiga atau lebih player tetap dapat berjalan walaupun Switch hanya memiliki dua controller yang tersedia.
