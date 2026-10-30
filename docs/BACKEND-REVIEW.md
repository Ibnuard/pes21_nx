# FootballNX Online League — Backend Review

## v114 � shop reproducible via API; patch and TEST catalog repair required

30 October 2026. TEST offer 1001/team 100 fails HTTP 500 PURCHASE_FAILED outside the Switch; wallet stays 45,500/revision 14, operation NOT_FOUND, no pending pack. Catalog roster for team 100 returns null. Local save deletion is not a fix.

Backend patch **58c9916** sudah di-push ke main sebagai BlekjekSudo. Go race suite, vet dan build lulus; client 104 tes/144 subtes dan tape baru 661 posisi playback lulus.

Backend patch: atomic checkout/debit/pool/receipt, known no-charge 422 errors, verified canonical membership repair CLI, and deterministic simulator v1.1.0 with causal ball paths, fouls/cards/corners. PostgreSQL is retained. Source patch requires deployment; TEST catalog relations must be checked/repaired from the exact paired SQLite. Preserve existing payment UUID/body and resume it after repair. Do not regenerate old sealed match tapes.

Full deployment and acceptance checklist: [backend v114 runbook](https://github.com/BlekjekSudo/fnx_server/blob/main/docs/V114-SHOP-SIMULATION.md). Client changes: [MANAGER_UI_SHOP_V114.md](MANAGER_UI_SHOP_V114.md). Local tests do not establish live post-deployment success.

## Retest deployment 25b61f1 — expiry dan refresh TEST lulus

29 Oktober 2026 WIB. Detail dan batas pengujian:
[MANAGER_BACKEND_RETEST_25B61F1.md](MANAGER_BACKEND_RETEST_25B61F1.md).
Status terbaru ini menggantikan status deployment pada arsip di bawah.

**Lulus live:** respons 401 sesi TEST lama tetap TEST; refresh sesi kini HTTP
200 dengan realm TEST pada data/envelope, demo_time=true, revision dan domain
clock sesuai bootstrap. Access token hasil refresh berhasil pada 14 endpoint.
Assertion realm salah tetap ditolak 403. Controller C menerima respons aktual
401 lalu refresh, mempertahankan autentikasi TEST dan melanjutkan safe GET.

Parser client menerima 13 payload, 0 ditolak; full recording ENDED 22 chunk
lolos 661 posisi playback. Suite controller client 50 tes lulus. Clock tetap
revision 45/cycle 19/LEAGUE_END, wallet tetap 44.000/version 13. Tidak ada
advance clock/join/pembelian/CDK atau mutasi PRODUCTION pada retest ini.

Temuan refresh dari deployment sebelumnya **ditutup**. Build NRO ulang selesai
memakai source serta pasangan runtime v113 existing; NRO identik dengan v113.
Paket ONLINE-VERIFIED-SIAP-COPY sudah diverifikasi. Acceptance perangkat
Switch fisik tetap diperlukan untuk tampilan dan perilaku runtime nyata.

## Arsip deployment f65e2b6 — sebelum koreksi refresh 25b61f1

29 Oktober 2026 WIB. Detail:
[MANAGER_BACKEND_RETEST_F65E2B6.md](MANAGER_BACKEND_RETEST_F65E2B6.md).
Status terbaru ini menggantikan status deployment pada arsip di bawah.

**Lulus live:** dua access token TEST lama sekarang mendapat 401 SESSION_EXPIRED
bermeta TEST/domain clock TEST. Respons aktual mencapai cabang refresh safe GET
pada controller C client. Smoke 14 endpoint berhasil; 12 payload diterima parser
client, 0 ditolak. Guard assertion salah tetap 403 dengan envelope TEST.
Clock tetap revision 45/cycle 19/LEAGUE_END, wallet 44.000/version 13.

**Belum lulus live — refresh sesi:** POST /auth/refresh sukses merotasi token,
namun data.environment kosong, meta.environment PRODUCTION, demo_time=false,
dan test_clock=null. Access baru sebenarnya tetap TEST dan bisa membuka
bootstrap TEST. Controller C menolak respons refresh aktual lalu kembali login.
Source melakukan query realm melalui transaksi yang sudah di-commit.

Perbaikan sudah dipush sebagai BlekjekSudo ke main backend:
[25b61f1](https://github.com/BlekjekSudo/fnx_server/commit/25b61f1f75832500eeb72f50372927439b7b673a).
Realm/status account/session kini dibaca sebelum commit, assertion salah tidak
merotasi token, dan sesi revoked/credential berubah/account nonaktif ditolak.
Tes dua database sintetis, race detector, go vet, dan build backend lulus.
**Deploy 25b61f1 lalu retest satu refresh TEST; tidak perlu NRO atau migrasi.**
Jangan replay refresh token lama setelah HTTP 200 karena token sudah dirotasi.

Retest ini hanya melakukan satu refresh TEST; tidak ada join/clock advance,
pembelian pack, CDK atau mutasi PRODUCTION. Tidak ada tes Switch fisik.

## Arsip deployment 8f7feee — empat temuan lama ditutup, koreksi auth berikutnya

29 Oktober 2026 WIB. Detail dan batas tes:
[MANAGER_BACKEND_RETEST_8F7FEEE.md](MANAGER_BACKEND_RETEST_8F7FEEE.md).
Bagian ini menggantikan status retest awal v113 di bawah.

**Lulus di server:** metadata replay join tetap TEST; cycle lama 16 kini
played=3/drawn=3/PTS=3; dua liga baru cycle 18/W1 dan 19/W2 selesai dengan
12 hasil resmi dan tabel yang sesuai. Schedule/standings kosong saat registration
baru sebelum/sesudah join sampai draw, tanpa membawa grup W1 ke W2. Clock
revision 27 → 45 melalui 18 advance unik, lookup serta replay tanpa mundur.
Player Feed mempunyai watermark valid; 18 news unik memiliki konteks waktu/W1/W2.

Dua join memberi tepat +3.000 cash/+1.000 monthly PTS total. Dua podium memberi
+4.000 monthly PTS sesudah FT dan +10.000 cash pada Minggu, tanpa kredit kedua
ketika replay/worker berjalan. Parser C client v113 menerima 184 payload dengan
0 penolakan; dua gate Player Feed 409 sebelum Match Day sah. Dua tape full
LIVE/replay 22 chunk lolos 1.322 posisi playback.

**Temuan tambahan — perlu deploy perbaikan auth terbaru:** token TEST yang
kedaluwarsa tetapi masih dikenali server menghasilkan HTTP 401 SESSION_EXPIRED
dengan meta.environment PRODUCTION. Payload aktual dikonfirmasi melalui
consume() client: ENVIRONMENT MISMATCH muncul sebelum refresh. Source
AuthMiddleware di repository backend sudah diperbaiki agar response error dari
session yang dikenali memakai realm/domain clock session sebelum validasi
401/403. AuthUser hanya diberikan setelah validasi lolos, dan header tidak bisa
mengubah realm token. Tes regresi PostgreSQL/race meliputi expired, revoked,
credential berubah, akun disabled, assertion salah, kedua realm, dan token asing.
Perbaikan auth sudah dipush sebagai BlekjekSudo: [f65e2b6](https://github.com/BlekjekSudo/fnx_server/commit/f65e2b68b0730593c45177964e2da25c789b073b).
Masih perlu deploy lalu retest token kedaluwarsa; tidak perlu NRO baru.

Semua mutasi server memakai akun/realm TEST. Tidak ada pembelian pack, redeem
CDK atau mutasi PRODUCTION. Semua skor liga baru 0–0 sehingga kontribusi pemain
dengan gol/assist positif belum diverifikasi live. Belum ada tes Switch fisik.
Clock DEV ditinggalkan pada hasil Minggu revision 45; saldo TEST 44.000.

## Arsip retest awal v113 — empat temuan sebelum perbaikan

29 Oktober 2026 WIB. Detail reproduksi dan acceptance terbaru:
[MANAGER_BACKEND_RETEST_V113.md](MANAGER_BACKEND_RETEST_V113.md). Bagian ini
menggantikan status retest v113 sebelumnya di bawah.

**Lolos:** Current/Past Season diterima parser client v113, field komponen nol
sudah ada, +500 PTS dan +1.500 NX Cash saat join masuk tepat sekali, autofill
1 manusia +3 BOT bekerja, fase Registration → Preparation → Match Day →
League End benar pada liga TEST baru, serta full recording LIVE diterima.
Snapshot page yang sama stabil; invalid page ditolak 400, assertion realm
yang salah ditolak 403, dan expected_revision stale ditolak 409.

**Belum selesai — prioritaskan empat temuan ini:**

1. Replay `POST /league/join` dengan key sama membawa `meta.environment:
   PRODUCTION` dan clock nyata, padahal token/header serta receipt pertama TEST.
   Client v113 menolaknya dengan ENVIRONMENT MISMATCH. Perbaiki envelope pada
   jalur generic idempotency replay; audit juga endpoint mutasi lain yang berbagi
   middleware, tanpa mengubah realm token atau mengirim kredit kedua.
2. Liga TEST baru cycle 16 sudah enam laga ENDED tetapi keempat tim tetap
   played=0. Player Feed sesudah Match Day/League End mengirim watermark 0,
   sehingga parser tetap menolak snapshot; news belum memuat hasil cycle baru.
   Lengkapi pipeline publikasi hasil/klasemen/feed/podium sebelum operasi clock
   menjadi SUCCEEDED. Array feed kosong tetap sah, watermark nol tidak sah.
3. Saat Registration cycle 16, `/league/schedule` masih mengirim fixture cycle
   15, sebelum maupun sesudah join. Parser membuangnya karena salah scope.
   Jika grup current cycle belum terbentuk, kembalikan [] tanpa fallback grup lama.
4. Advance pertama setelah deployment memundurkan domain clock TEST sekitar
   126 menit: server_now_ms 1793779303237 → test_now_ms 1793771760000.
   Uji/migrasikan clock existing dan hitung milestone dari now realm terkini.
   Advance berikutnya pada state baru tidak menunjukkan rollback dalam retest.

Player Feed lama cycle 15 kini diterima saat watermark valid; pada cycle baru
masih gagal karena nol. Jadi koreksi Player Feed belum ditutup sepenuhnya.
Tidak ada perubahan source client/NRO pada retest ini; 238 hash source/build
tetap cocok dengan paket client v113. Seluruh mutasi tes memakai token dan
header TEST. Tidak ada pembelian pack, redeem CDK atau mutasi berheader PRODUCTION.

## Retest v113 — deployment V112 tersedia, tiga koreksi kontrak masih diperlukan

29 Oktober 2026 WIB. Retest HTTPS menggunakan akun operator TEST yang telah
diizinkan. Bagian ini menggantikan status deployment pada catatan v112/v111 di
bawah; kontrak produknya tetap berlaku. Tidak ada pembelian pack, redeem CDK,
registrasi akun baru atau perubahan data PRODUCTION dalam retest ini.

**Sudah terverifikasi:** capability `monthly_ranking_v1` dan `player_feed_v1`
aktif; endpoint Current/Past Season merespons 200. Parser C produksi menerima
bootstrap, profil, standings, schedule, news kosong, Past Season, juara W1/W2,
squad, Game Plan dan full playback. GET playback fixture 55 memuat 22 chunk,
659 frame dan 470 event; 661 posisi playback lolos pemeriksaan skor/touchline.
Fixture 57 saat LIVE juga mengirim satu bundle penuh (22 chunk), bukan stream.
Clock NEXT_MILESTONE TEST berhasil revision 15 → 16; lookup dan POST replay
dengan UUID/body sama mengembalikan revision serta waktu receipt yang sama.

**Masih perlu diperbaiki sebelum semua menu V112 bisa digunakan:**

1. **P2 — Current Season tidak mengirim `participation_points` ketika nol.**
   Respons aktual memiliki `points: 4000, podium_points: 4000`, tetapi field
   partisipasi hilang. Parser menolak payload ini sesuai kontrak v112, sehingga
   Current Season belum dapat dibuka. Hilangkan `omitempty` untuk kedua komponen
   poin pada DTO Current Season; selalu kirim integer termasuk nol. Contoh sah:
   `"points":4000,"participation_points":0,"podium_points":4000`.
   Retest ini tidak membuktikan ledger partisipasi salah: nol bisa berasal dari
   waktu kredit bulan sebelumnya. Jangan menambah saldo/poin untuk memperbaiki
   masalah serialisasi. Tambahkan tes endpoint untuk kombinasi nol, hanya +500,
   hanya podium lintas bulan, dan keduanya; pastikan jumlah komponen = points.

2. **P2 — Player Feed belum sesuai kontrak v111.** Root hanya berisi
   `rising_stars` dan `top_scorers`, tanpa `cycle_id`/`published_through_ms`.
   Item menggunakan `match_ovr` alih-alih `snapshot_ovr`, mengandung goals=0
   dan assists=0, serta player_key yang sama muncul berulang untuk klub BOT.
   Parser menolak seluruh snapshot. Kirim cycle dan watermark publikasi,
   `snapshot_ovr` dari roster terkunci, dan statistik event yang sudah tayang.
   Top Scorers wajib goals>0. Rising Stars wajib OVR<=69 serta goals+assists>0.
   Gabungkan canonical player_key sesuai kontrak, bukan mengisi daftar dengan
   semua pemain roster atau menduplikasi starter BOT. Bila belum ada kontribusi,
   kirim kedua array kosong dengan cycle/watermark valid. Pertahankan urutan dan
   batas 32; uji tanpa gol, kontribusi nyata, retry worker dan anti-spoiler.

3. **P2 — state fase tidak mengikuti clock TEST dan jadwal resmi.** Bootstrap
   dan `/league/status` berulang kali mengirim cycle 15 `state: PREPARATION`
   pada server_now_ms=1793769060000. Jadwal cycle yang sama sudah mempunyai
   fixture ENDED dan pertandingan berikut SCHEDULED; fase resmi berjalan dari
   1793768400000 hingga 1793774460000. Setelah NEXT_MILESTONE sukses,
   server_now_ms sekitar 1793771100000 dan fixture 57 LIVE, tetapi state tetap
   PREPARATION. Turunkan state, phase_started/ends dan status fixture dari clock
   realm yang sama, dengan transisi atomik atau projection bersama. Pada jam
   tersebut state harus MATCH_DAY; sesudah siaran terakhir gunakan League End.
   Uji bootstrap/status/schedule sebelum kickoff, saat LIVE, FT terakhir dan
   next registration. Client v113 memakai batas siaran resmi sebagai fallback
   akses Match Centre; ini tidak menggantikan koreksi state backend.

`/news` masih null meskipun round pertama sudah diterbitkan dan standings
menunjukkan played=1. Null diterima sebagai empty state, bukan parser error.
Periksa outbox/backfill MATCH_RESULT dan LEAGUE_LEADER dari hasil resmi sesuai
v111 agar Club Feed terisi; belum ada bukti forward-event baru setelah deployment.

Empat bug client dari audit kompetisi sudah diperbaiki di v113 dan tidak
memerlukan endpoint baru. Lihat [COMPETITION_FIXES_V113.md](COMPETITION_FIXES_V113.md).
Bukti wire/token/tape berada di direktori lokal ignored; tidak dilampirkan dalam
handoff publik. Jangan menutup temuan payload di atas hanya berdasarkan HTTP 200:
acceptance harus menjalankan DTO yang sama dengan parser client.

## Revisi produk v112 — ranking bulanan, empat tile LEAGUE dan badge LIVE

Kontrak terbaru: [MANAGER_HUB_V112.md](MANAGER_HUB_V112.md). Ini permintaan
implementasi backend, bukan hasil retest deployment. Bagian v111 tetap berlaku
untuk kalender, registration, Club Feed dan Player Feed, dengan revisi berikut:

1. Tab LEAGUE: atas kiri **League Ranking History** (juara W1/W2), atas kanan
   **League Ranking** bulanan; bawah kiri Logout, bawah kanan League Guide.
2. Ganti aturan Overall Rank 14 hari dengan bulan kalender WIB. Partisipasi
   **+500 PTS** per liga, tambahan podium **2.000 PTS** untuk juara 1,
   **1.500 PTS** juara 2, **1.000 PTS** juara 3. Contoh total juara 1 satu liga:
   2.500 PTS. League Points 3/1/0 dan wallet NX Cash tetap terpisah.
3. Sediakan capability `monthly_ranking_v1`,
   `GET /ranking/monthly/current` dan `GET /ranking/monthly/past`,
   pagination 50 dengan snapshot stabil. Current menampilkan seluruh peserta;
   Past hanya juara 1 setiap bulan selesai. Reset tanggal 1 pukul 00:00 WIB.
   Detail DTO, error, ledger MySQL, concurrency dan acceptance ada di v112.
4. Tambahkan `monthly_ranking` nullable pada profil, serta `league_label` W1/W2
   pada riwayat juara liga existing. Jangan relabel RP lama sebagai poin bulanan.
   BOT tidak masuk global monthly ranking; history juara liga tetap boleh BOT.
5. Badge **LIVE** di tile fase hanya ketika Match Day punya siaran LIVE dalam
   grup berjalan. `/league/schedule` harus konsisten dengan current cycle dan
   clock realm, memuat `broadcast_start_ms`, `broadcast_end_ms`, `duration_ms`.
   Status LIVE mengikuti jam siaran, bukan waktu simulasi skor selesai.
   Client refresh ringan tiap 30 detik/di batas siaran, tidak streaming.
6. +500 diberikan tepat sekali saat join; podium saat tabel akhir resmi selesai
   tayang. Timestamp peristiwa menentukan bulan kredit. Hadiah NX Cash tetap
   Minggu. Ledger unique lintas season mencegah kredit ulang saat retry/reset.

Perubahan tampilan client: tanpa A TO JOIN, subtitle Club Feed dihapus, TODAY
dirapikan, statistik Player Feed dan hadiah poin dipisahkan menurut label.
DEV OFFLINE tetap tersedia untuk mencoba alur. Capability bulanan hanya boleh
diaktifkan setelah backend memenuhi kontrak; tanpa flag, client memberi popup
belum tersedia. Temuan live v110 di bawah belum ditutup oleh revisi UI ini.

## Revisi produk v111 — hub, pendaftaran, countdown dan feed

29 Oktober 2026. Kontrak implementasi lengkap dan acceptance ada di
[MANAGER_HUB_V111.md](MANAGER_HUB_V111.md). Bagian ini adalah permintaan perubahan
backend baru, **bukan klaim bahwa deployment sudah mendukungnya**. Temuan retest
v110 di bawah tetap berlaku sampai diverifikasi lagi.

Prioritas agent backend:

1. Perbaiki current-cycle/membership v110, lalu tambahkan `phase_started_at_ms`
   dan `phase_ends_at_ms` pada bootstrap/status. Semua waktu dan countdown
   menggunakan clock realm. Status `user_joined` harus benar bahkan sebelum
   grup/fixture terbentuk.
2. Registration tile menunjukkan countdown serta status pendaftaran. Belum
   terdaftar → A membuka konfirmasi; setelah terdaftar → A hanya popup penjelasan.
   Join/bonus +1.500 wajib idempoten untuk membership yang sama. Tidak ada lagi
   helper X untuk Join atau Logout; Logout adalah tile tab LEAGUE.
3. Enrich `GET /news`: kartu signing dengan nama pemain canonical, hasil match
   dengan dua klub/skor, serta pemuncak klasemen. Emit dari transaksi resmi;
   jangan bocorkan hasil sebelum full time. Format/type/SQL di dokumen v111.
4. Tambahkan `GET /league/player-feed` dan capability `player_feed_v1`. Dua list:
   Top Scorers dan Rising Stars berbasis kontribusi pemain OVR <=69. Endpoint
   hanya dibuka mulai Match Day sampai League End, stats sesuai event sudah tayang.
5. Schedule UI adalah tujuh hari WIB: Senin daftar, Selasa persiapan, Rabu match,
   Kamis daftar, Jumat persiapan, Sabtu match, Minggu overview/hadiah. Match Centre
   LIVE/SCHEDULED/ENDED tetap existing, dibuka lewat tile fase Match Day/League End.
   Tidak perlu endpoint kalender baru. Pertahankan rewards/history/Overall Rank
   di Club Profile; Trade History hanya popup Upcoming, belum perlu endpoint.

Client v111 memiliki parser kontrak baru, fallback respons news legacy dan gate
capability Player Feed. Backend harus menambahkan tes fase penuh, duplicate join,
publikasi feed, isolasi TEST/PRODUCTION dan statistik tanpa future-score leak
sebelum mengaktifkan capability. Kontrak full recording v110 tetap dibutuhkan.

## Retest v110 — kontrak yang masih perlu ditangani

29 Oktober 2026 WIB. Bagian ini menggantikan status temuan historis di bawah.
Retest memakai akun operator **TEST** yang sudah diizinkan. Tidak ada pembelian
pack, redeem CDK, akun baru, atau perubahan PRODUCTION. Bukti respons, credential,
dan rekaman mentah disimpan lokal/ignored, bukan dalam handoff publik.

### Hasil aktual

| Pemeriksaan | Hasil |
| --- | --- |
| Close pendaftaran W1 | NEXT_MILESTONE revision 12→13: 1 manusia + 3 BOT, empat klub, enam fixture, klasemen empat baris |
| Kickoff W1 | Revision 14, Rabu 4 Nov 2026 12:00 WIB: fixture 55/56 LIVE, empat berikutnya SCHEDULED |
| Full time pertama | Revision 15, Rabu 12:11 WIB: fixture 55 ENDED, report dan semua 22 chunk HTTP 200 |
| Parser rekaman client | 659 frame, 470 event; semua 22 chunk dan header/events lolos. Playback diperiksa pada 661 posisi waktu, termasuk pergantian babak |
| Detail touchline | 468/470 event memiliki actor_name, 435 recipient_name; masalah nama pemain pada v109 sudah diperbaiki |
| Save Game Plan nyata | Body dari encoder C mengubah formasi/koordinat, GET mengonfirmasi XI/bench/taktik/set pieces. Susunan semula dipulihkan; revision 1→2→3 |
| Snapshot pertandingan | recording_hash fixture 55 tetap sama setelah edit dan pemulihan Game Plan |
| Atlas | Schedule, standings dan opponent 31 sudah memberi presentation_team_id. Client sebelumnya belum memakainya dengan benar |
| Wallet | Tetap 19.500 NX Cash/version 6 sepanjang retest ini |

### P1 — current league/status masih mengembalikan cycle lama

Pada Selasa 3 Nov dan Rabu 4 Nov, `bootstrap.league=null`, sedangkan
`GET /league/status` mengembalikan **cycle 12 / W1 / REGISTRATION /
user_joined=false / waiting_entry_count=0**. Padahal klub yang sama sudah mempunyai
entry 37 pada liga W1 baru, schedule 55–60/group 10, empat klub dan pertandingan LIVE.
Metadata TEST clock benar; state/membership yang dikembalikan masih salah.

Perbaiki query current window berdasarkan clock realm, kemudian join membership
untuk **cycle yang sama**. Jangan mengambil row REGISTRATION lama yang belum
ditutup, atau menjadikan liga terakhir diikuti sebagai current window. Bootstrap,
status, standings, profile, schedule dan mutation JOIN harus konsisten. Jangan
memberikan bonus kedua karena client menerima membership palsu `false`.

Tambahkan field epoch-ms pada object liga di bootstrap/status:

| Field | Makna |
| --- | --- |
| `registration_open_ms` | Awal Senin untuk W1 atau Kamis untuk W2 |
| `registration_close_ms` | Batas masuk liga; Selasa/Jumat 00:00 WIB |
| `first_kickoff_ms` | Kickoff pertama liga, Rabu/Sabtu |
| `last_full_time_ms` | Akhir fixture terakhir liga |
| `rewards_at_ms` | Waktu settlement Minggu; terpisah dari full time W1/W2 |
| `next_registration_at_ms` | Jendela pendaftaran berikutnya |

Client v110 membaca field ini. Bila belum tersedia, aturan mingguan diberi label
sebagai aturan, bukan tanggal terkonfirmasi. Waktu kickoff/full time yang sudah
ada di schedule ditampilkan. Jika fixture klub sudah ada pada window berjalan
tetapi status masih mengaku belum terdaftar, client tidak menawarkan JOIN lagi:
hub membuka timeline dan menjelaskan ketidakselarasan status server.

Acceptance: Senin join → Selasa prep → Rabu LIVE/full time → Kamis join W2 →
Jumat prep → Sabtu LIVE/full time → Minggu hadiah → Senin W1 baru. Uji endpoint
di setiap langkah, bukan hanya receipt advance. State TEST akhir retest ini
revision 15/Rabu 12:11, bukan satu
minggu penuh yang sudah lulus acceptance.

### P1 — sediakan satu payload pertandingan penuh untuk playback lokal

Permintaan produk sekarang: **satu fetch setelah kickoff memberi rekaman penuh
90 menit pertandingan**. Client menampilkan bagian yang sesuai waktu tayang;
replay memakai rekaman yang sama. Tidak ada stream video, engine COM vs COM,
simulasi ulang per penonton, atau fetch per gerakan dot.

Deployment sekarang belum menyediakan kontrak tersebut: pada kickoff fixture 55,
header LIVE/watermark 0, chunk 0 tersedia, chunk 21 ditolak HTTP 403
`CHUNK_FUTURE_LOCKED`, events hanya kickoff. Setelah ENDED, semua data tersedia.
OpenAPI dan capabilities belum mengiklankan bundle penuh. Client v110 tetap
mendukung API lama, memperbaiki fetch chunk 0 pada watermark 0, cache 22 chunk,
interpolasi antar-chunk, serta retry/error yang dapat ditinggalkan.

**Kontrak baru yang sudah didukung client v110, aktif hanya dengan capability:**

```json
{"capabilities":{"match_recording_bundle":true}}
```

Tambahkan flag tersebut pada `GET /me/bootstrap` hanya setelah endpoint berikut
benar-benar siap, untuk TEST maupun PRODUCTION yang mendukungnya:

`GET /api/v1/matches/{fixture_id}/playback`

Header Bearer, X-FNX-Environment, online version/catalog tetap sama. Respons 200:

```text
{
  data: {
    playback_policy: "FULL_RECORDING",
    header: { ...DTO recording/header yang sudah ada... },
    chunks: [ { index: 0, frames: [...] }, ... { index: 21, frames: [...] } ],
    events: [ ...seluruh timeline hingga full time... ]
  },
  meta: { environment, server_now_ms, real_server_now_ms,
          online_version, api_schema_version, request_id }
}
```

Ketentuan yang divalidasi client:

- `header.fixture_id` cocok dengan fixture yang dibuka; hash SHA256 lowercase
  64 karakter tetap untuk rekaman tersebut; recording_version tetap dikirim.
- duration_ms = 660000, chunk_duration_ms = 30000, chunk_count = 22;
  broadcast_start_ms adalah waktu tayang resmi. State LIVE atau ENDED.
  current_watermark_ms tetap progress tayang; **bukan batas isi bundle**.
- `chunks` tepat 22 item terurut index 0–21, masing-masing 1–128 frame. Frame
  memakai schema existing `{at_ms,bx,by,h:[...],a:[...]}`. Koordinat integer
  x 0–105000/y 0–68000; maksimal 11 pemain per sisi, shirt_number optional.
  Timestamp naik dalam chunk, berada dalam interval chunk yang sesuai.
- `events` maksimal 512, terurut at_ms, mencakup seluruh pertandingan hingga
  duration_ms. Tetap kirim game_second 0–5400, kind, side, actor_name,
  recipient_name dan identitas pemain sesuai snapshot.
- Batas respons **4 MiB setelah decompression**, maksimal 360.000 token parser.
  Gzip didukung. Rekaman nyata fixture 55 bila digabung berukuran 633.588 byte,
  659 frame dan 470 event, sehingga jauh di bawah batas.
- Sebelum kickoff: error MATCH_NOT_STARTED; setelah kickoff semua chunk/event
  harus tersedia sekaligus. Jangan mengaktifkan flag bila bundle belum lengkap.
- Client melakukan satu GET, menyimpan tape dalam RAM dan tidak mem-poll header,
  chunks atau events selama tape aktif. LIVE mulai pada
  clamp(meta.server_now_ms − broadcast_start_ms,0,duration_ms), lalu berjalan
  dengan monotonic clock lokal. Replay mulai 0 dan dapat pause/seek. Skor, stats,
  komentar dan touchline hanya memakai event sampai cursor saat ini.
- Rekaman immutable berdasarkan roster/taktik yang dikunci sebelum compute.
  Save Game Plan setelah compute tidak boleh mengganti rekaman fixture tersebut.

Assembly lokal dari 22 chunk deployment sudah lolos parser dan 661 posisi
playback, tetapi **ini belum merupakan bukti endpoint bundle terdeploy**.
Perbarui OpenAPI dengan schema request/response yang lengkap dan uji dua client
masuk pada waktu berbeda: keduanya harus berada pada offset LIVE yang sama,
tanpa request lanjutan setelah bundle diterima.

### P1 — clock TEST perlu berjalan ketika menonton LIVE

Setelah advance ke kickoff, beberapa pembacaan terpisah tetap memberi
server_now_ms = 1793768400000 dan watermark = 0 meski real_server_now_ms bergerak.
Karena itu client yang mematuhi watermark tidak dapat menonton sampai advance
berikutnya. Client v110 sekarang menampilkan frame kickoff dan pemberitahuan
`TEST CLOCK IS PAUSED`, bukan layar buffering tanpa akhir.

Gunakan anchor virtual + elapsed real time dengan rate 1 ketika LIVE; NEXT_MILESTONE
memindahkan anchor secara atomik/revisioned, dan seluruh worker/DTO mengambil
clock yang sama. Saat advance selesai, envelope harus memakai waktu anchor baru.
Jangan mengatasi ini dengan memberi waktu mulai berbeda untuk setiap penonton.
Sertakan pengujian join terlambat dan dua sesi bersamaan pada TEST.

### P2 — identitas presentasi pada champions dan kelengkapan portrait

`/ranking/overall` mengirim account_id, club_name, ranking_points dan rank,
tetapi belum mengirim club_id/presentation_team_id. Client sekarang membaca
ranking_points (8.000 RP pada akun TEST), bukan field lama rp. Untuk akun sendiri,
bootstrap membuktikan mapping account → club → presentation team. Akun lain tidak
boleh dipetakan dari kemiripan nama atau menyamakan account_id dengan club_id.
Tambahkan kedua ID tersebut pada setiap ranking entry supaya crest dan navigasi
profil tersedia untuk semua klub. Profile juga perlu mengirim rank yang konsisten:
profile TEST memberi overall_rank=null saat tabel memberi rank=1. Client dapat
memakai tabel yang sudah dimuat ketika rank profile belum tersedia.

`/ranking/champions` saat ini memberi cycle_id/group_id/club_name/is_bot/
settled_at, tetapi tidak memberi club_id atau presentation_team_id. Tambahkan
keduanya agar honours menggunakan atlas yang benar dan dapat membuka profil.
Gunakan club_id untuk akun/klub, presentation_team_id untuk atlas; jangan tukar
fungsi kedua ID tersebut atau mencocokkan nama teks sebagai identitas.

Audit portrait memperjelas temuan v109: dari 18 starter TEST, **6 punya foto
lokal, 8 binding menunjuk siluet netral, 4 belum punya binding portrait**. Jadi
14 binding bukan 14 foto. Backend/local canonical player_key sudah cocok;
mengganti ID numerik dengan BaseId mentah bisa menampilkan wajah pemain lain.
Client v110 menyediakan placeholder untuk semua slot dan memutar antrean loader
agar satu file yang tidak tersedia tidak menahan portrait pemain berikutnya.

Jika starter harus selalu mempunyai foto, tambahkan status portrait terverifikasi
pada catalog/manifest dan gunakan dalam eligibility starter OVR 60–69. Ketersediaan
file saja bukan bukti wajah benar; tetap ikuti BaseId+fingerprint dan kebijakan
aset. Jangan mengganti kepemilikan/identitas starter yang sudah dimiliki user.
Penambahan foto nyata memerlukan pembaruan asset lokal yang dipasangkan, bukan
perubahan URL API atau peminjaman wajah dari slot donor.

### Perubahan FE v110

Game Plan sendiri sekarang editor draft dengan swap XI/bench, posisi, formasi,
taktik, captain/set pieces dan reset draft; hanya keluar dengan draft berubah
yang mengirim PUT. GET memverifikasi hasil; timeout/conflict mempertahankan draft
dan UUID/body untuk retry. Game Plan lawan tetap snapshot tanpa empat tombol
aksi, dengan satu keterangan data terakhir.

Hub memakai preview klasemen 3 besar, fixture berlogo, crest profil dan data feed
server. Menu Competition memisahkan rewards, champions, riwayat klub, overall
rank 14 hari dan guide. Schedule mempunyai logo kedua klub, tanggal/jam WIB dan
bagian LIVE/SCHEDULED/ENDED. Tabel kosong mempunyai penjelasan fase. Semua ini
telah dirender lewat fungsi C produksi dengan payload deployment, bukan hanya
mock tampilan. Tes perangkat Switch tetap diperlukan untuk GPU/input/jaringan.

Verifikasi host: 59 tes dan 131 subtes lolos; 15 halaman dirender dengan fungsi C
produksi dan data API yang tersimpan. Build Switch memakai `build-wsl.ps1`.

## Retest v109 — rekaman sudah terbaca; current registration window masih stale

29 Oktober 2026 WIB. Retest setelah update backend, sekaligus perbaikan FE dari
hasil tes Switch. Hanya memakai akun DEV TEST yang sudah diizinkan; tidak
membuat akun, membeli pack, menukar voucher atau memajukan clock PRODUCTION.
Bukti privat tetap ignored di `local-debug/manager-frontend-v109/`.

**Rekaman TEST yang sebelumnya rusak sekarang lolos parser client.** Fixture 31
dan 36 mengembalikan header `ENDED`, watermark 660000, chunk awal dan report HTTP
200. Semua 22 chunk fixture 31 serta 470 event berhasil dibaca parser C yang sama
dengan client. Total 30 payload deployment, termasuk bootstrap, profile, squad,
Game Plan, status dan schedule, lolos pemeriksaan tersebut.

Advance NEXT_MILESTONE, FINISH_WEEK dan NEXT_MILESTONE berikutnya mengembalikan
SUCCEEDED dengan revision 13, 14 dan 15; waktu menjadi 3 November, Minggu
8 November 09:00 WIB, lalu Senin 9 November 00:00 WIB. Namun bootstrap maupun
`GET /league/status` tetap menunjuk cycle 6, W2, `SETTLED`, `user_joined=true`,
`next_registration_at=null` pada ketiga snapshot. Schedule tetap enam hasil W2.

### P1 — Pisahkan current calendar/window dari liga terakhir yang diikuti

Pada Senin baru, status harus memberi window pendaftaran baru yang benar,
termasuk cycle/label/state dan membership untuk cycle tersebut. Liga lama yang
SETTLED tetap tersedia sebagai riwayat, bukan menggantikan current window.
Pastikan JOIN untuk W1 berikutnya tersedia, bonus partisipasi hanya sekali, dan
NEXT_MILESTONE berjalan melalui seluruh kickoff/full time W1 dan W2. Client
menampilkan state server apa adanya; tidak membuka pendaftaran lewat jam lokal.

Retest ini dimulai dari akun yang sudah mempunyai liga settled. Karena itu,
hasil ini belum membuktikan satu siklus baru join→W1→W2→hadiah end-to-end. Saldo
tetap 18000/version 5 sepanjang tiga advance; tidak ada klaim payout baru.

### P2 — Lengkapi nama actor/recipient pada event pertandingan

470 event fixture 31 memuat instance ID, tetapi tidak satu pun mempunyai
`actor_name`. Sertakan nama/identitas katalog dari snapshot kedua tim, termasuk
untuk lawan/BOT, agar Touchline dapat menyebut pencetak gol dan pemain yang
terlibat tanpa menebak dari roster milik penonton. Client menerima timeline ini,
tetapi tanpa nama server, detail akan tetap memakai nama klub sebagai fallback.

### Temuan FE yang ditangani di client v109

- Loader GPU portrait salah membaca provider offline, bukan provider online
  aktif; permintaan portrait untuk 18 slot Game Plan juga belum dipasang.
  Mapping canonical/runtime ID cocok: 14 dari 18 starter DEV punya binding
  portrait lokal, empat memang belum memiliki portrait pada katalog pasangan.
- Tick frontend sebelumnya berhenti saat loading aktif. Akibatnya receipt clock
  tidak dikonsumsi dan popup milik clock tidak pernah ditutup. Tick sekarang
  berjalan sebelum input gate; timeout tetap menyimpan recovery ID.
- Shop recovery sekarang membaca UUID/body lama, memanggil
  `/shop/operations/{idempotency_key}`, dan dapat retry **request yang sama**.
  Status nyata untuk UUID asing adalah HTTP200 `status=NOT_FOUND`; bentuk receipt
  COMPLETED menggunakan `operation=SHOP_PURCHASE` dan `response` dari kontrak
  deployment. Tidak menghapus bukti pembayaran yang belum terkonfirmasi.
- Kegagalan menyimpan journal sebelum dispatch tidak mengirim POST atau
  menandainya sebagai pembayaran terkirim. Jalur error/leave/retry diuji dengan
  kegagalan rename; penyebab filesystem pada SD pengguna belum dapat dibuktikan
  dari screenshot saja. Record rusak tetap dipertahankan untuk dukungan.
- Profil online memakai layout crest dan enam submenu, ranking/poin/RP server.
  Header membedakan fase liga dengan status terdaftar. Font kini menampilkan
  underscore User ID, sementara isi request login tetap identik.

Pengujian host dan build kandidat tidak menggantikan tes SD/filesystem,
portrait GPU, input dan internet di Switch nyata.

## Retest v108 — pipeline utama membaik; rekaman TEST dan rotasi window belum benar

28 Oktober2026 WIB, setelah perbaikan clock backend. Memakai akun DEV TEST dan
akun QA PRODUCTION yang sama; tidak membuat akun baru, redeem CDK lagi, atau
mengubah clock produksi. Source/NRO client tetap v107. OpenAPI masih45 operasi,
SHA256 `3bf97f0ec384d8ef4d40042c5859e5072bd9e2c6e1c77887c2efcd53c644ce61`.
Bukti privat: ignored `local-debug/manager-backend-retest-v108/`.

**Blocker v107 bahwa clock hanya maju tanpa membuat BOT/fixture atau payout
sudah tertutup pada skenario1 manusia ini.** Sekarang close, autofill, compute,
hasil dan settlement benar-benar menghasilkan perubahan domain. Tetapi belum
lulus keseluruhan prep→LIVE→dua liga/minggu→minggu berikutnya. Dua pekerjaan
backend di bawah masih diperlukan; jangan menandai seluruh ONLINEDEV selesai.

### Yang lolos langsung v108

| Transisi TEST yang dicoba | Hasil domain, bukan hanya HTTP |
| --- | --- |
| Senin2 November00:00, Join cycle5 W1 | Entry13, +1500 sekali; wallet11500/v3 →13000/v4; replay Join tidak menggandakan bonus |
| Selasa3 November00:00, NEXT_MILESTONE | PREPARATION;1 HUMAN+3 BOT,4entry,6fixture/3round dan standings played0 |
| Rabu4 November12:11 | Dua fixture round1 ENDED, tiap klub played1, skor tersedia |
| Kamis5 November00:00 | Semua6 fixture ENDED, setiap klub played3, klasemen terisi; tidak ada podium cash dini |
| FINISH_WEEK → Minggu8 November09:00 | Champion cycle5/group4 dicatat, credit5000 sekali; wallet13000/v4 →18000/v5 |
| Replay Finish Week + lookup; replay close lama |200; tidak menggandakan BOT/fixture/bonus/hadiah, tidak mengembalikan clock lama |
| Key sama/body berbeda; stale revision |409 IDEMPOTENCY_CONFLICT dan409 REVISION_CONFLICT |
| Envelope clock setelah sukses |meta.server_now_ms sekarang cocok dengan data.test_now_ms; mismatch lama sudah diperbaiki |
| Akun QA produksi setelah semua advance TEST |Wallet tetap2500/v6; squad, collection26, plan dan pending sama dengan snapshot awal |

Clock TEST revision5 →14 pada seluruh langkah tes. Snapshot TEST awal sebelum
mutasi kali ini sudah berbeda dari akhir v107: wallet11500/v3, belum join active
cycle5, honours cycle1 sudah ada. Itu keadaan deployment/operator sebelum tes,
bukan efek atau refund CDK oleh pengujian v108. Tidak menguji ulang kredit CDK.
Seluruh6 pertandingan skenario ini0–0; ini bukti lifecycle/results, bukan
acceptance balancing simulator atau OVR corpus.

### P1 — read rekaman TEST memakai state/watermark yang tidak mengikuti clock TEST

Fixture19 dari group4 dijadwalkan Rabu4 November12:00 WIB. Pada snapshot Rabu
12:11 dan Kamis00:00, `/league/schedule` sudah menyebut ENDED. Setelah settlement
Minggu8 November09:00, `/matches/19/report` juga200 dan berisi statistics/input
hash/strength. Tetapi pembacaan rekaman pada waktu TEST yang sama:

- `/matches/19/recording/header`:200, **SCHEDULED**, watermark0; broadcast_start
  1793768400000, duration660000,22chunk. Header hash tetap
  `0f545b972e1db132cda347cab8c7ad3668f5a11d15263b855d59cfc59fd9ece6`.
- `/matches/19/recording/chunks/0` dan `/10`:404 CHUNK_NOT_FOUND dengan pesan
  **MATCH_NOT_STARTED**, meski report sudah tersedia setelah fulltime.
- `/matches/19/events`: hanya kickoff at_ms0, bukan seluruh event ended.
- Fixture24 dari round3 sama: header SCHEDULED/watermark0 sesudah seluruh6
  pertandingan selesai. Ini bukan boundary tepat pada satu kickoff saja.

Meta seluruh respons mengumumkan TEST dan server_now_ms1794103200000, sehingga
payload header sendiri tidak konsisten dengan domain clock/envelope/report.
Saat berada tepat di kickoff, header juga SCHEDULED dan chunk0 ditolak; tidak
ada LIVE TEST yang berhasil diobservasi pada langkah yang tersedia. Clock TEST
tetap statis di antara request walau real_server_now_ms bertambah; audit anchor
normal1x atau sediakan milestone LIVE yang dapat ditonton sesuai kontrak.

**Dampak Switch:** watch parser v107 menerima LIVE/ENDED saja. Match Centre
dapat menampilkan hasil ENDED, tetapi header tetap SCHEDULED membuat watch
ditolak; chunk404 mencegah dots/replay. Jangan mengubah client agar mengarang
watermark atau mengabaikan gate future-data untuk menutupi masalah ini.

Periksa clock dependency di recording header, chunks, events dan spoiler/cache
read model. Kemungkinan read path masih memakai waktu nyata/clock yang berbeda
dari pipeline TEST; ini inferensi dari HTTP, bukan diagnosis source yang telah
dibuktikan. Gunakan principal realm/domain clock sama pada semua endpoint.
Setelah end: header ENDED, watermark660000, semua22chunk dan events tersedia,
hash tetap. Saat LIVE: watermark/frame/event sama pada dua viewer di at_ms sama.

Request IDs: header19 `req_917d055065d31108`, chunk0
`req_85f018c6826867b0`, events `req_0cc846e590e5649b`, report
`req_23582e1419140d65`. Payload snapshot tersebut disimpan lokal untuk retest.

### P1 — milestone melewati laga lain; W2 dan cycle berikutnya tidak ditawarkan

- STEP04 berada Rabu4 November12:11, masih ada4fixture SCHEDULED dengan kickoff
  12:45 dan13:30. NEXT_MILESTONE STEP05 langsung **Kamis00:00**, menjadikan4
  fixture itu ENDED tanpa berhenti pada kickoff/fulltime mereka. Target NEXT
  harus berasal dari milestone domain/fixture yang masih jatuh tempo; bukan
  daftar jam12:00/12:11 harian yang mengabaikan round selanjutnya.
- Pada Kamis00:00, Jumat00:00 dan Sabtu12:00, bootstrap serta `/league/status`
  masih menunjuk **cycle5 W1 PREPARATION, user_joined=true** walau seluruh6fixture
  sudah ENDED. Registration W2 Kamis tidak ditawarkan. Join W2 via POST tidak
  dipaksakan dalam tes ini; client mengikuti state yang dipublikasikan server,
  sehingga tombol Join W2 tidak akan tersedia.
- Sesudah Sunday payout, bootstrap.league=null, `/league/status`200 data=null,
  `/league/schedule`kosong. Pada **Senin9 November00:00** sesudah advance
  berikutnya, status masih null; cycle pendaftaran berikutnya belum muncul.
  Client null-bootstrap memang memanggil league/status, tetapi tidak dapat
  membuat pendaftaran dari response null. Empty Sunday bukan alasan untuk
  menghilangkan registration Senin berikutnya.
- `/league/standings` tetap memuat standings cycle5 sementara active status/
  schedule kosong. Pada registration cycle5 sebelum close, endpoint ini sempat
  memuat entries9..12 dari cycle sebelumnya, sedangkan current entry13. Pastikan
  endpoint current-cycle dan history memakai cycle/group yang jelas.

Perbaiki pemilihan active registration window berdasarkan kalender TEST,
rotasi W1→W2 tanpa menunggu payout Minggu, phase yang mengikuti progress match,
serta provision cycle mendatang secara idempoten. Full schedule/replay lama
harus tetap dapat dibaca lewat history/cycle selector yang terdokumentasi.
Jika tidak ada active league, berikan status terstruktur CLOSED/OVERVIEW dan
next_registration_at; jangan membuat client menebak tanggal atau membuka Join
sendiri. Pada Senin/Kamis, window yang benar harus tersedia.

Request IDs: STEP05 `req_d931da0c1d027917`, STEP06
`req_ddd181ac3d33cf2c`, STEP07 `req_c5366832b9ddc79a`, Sunday finish
`req_5954dff3e3518c83`, Monday berikutnya `req_e59bfef19c659f19`.

### Acceptance untuk retest selanjutnya

1. Pertahankan bukti BOT4/6fixtures/hasil/bonus/reward once yang sudah lolos.
2. Dua viewer TEST LIVE mendapatkan header LIVE/watermark bergerak dan chunk/
   events yang sama; setelah end22/22chunk tersedia, header/report/schedule sama.
3. NEXT berhenti di seluruh round dan halftime/fulltime yang relevan; Finish
   Week boleh melewati penantian sambil menjalankan pipeline sampai target.
4. Kamis membuka W2 meski W1 sudah selesai namun belum payout; Join W2 memberi
   +1500 sekali. Jumat prep, Sabtu match; Minggu settle dua league yang diikuti.
5. Senin berikutnya membuka registration cycle baru. Current standings tidak
   mengembalikan entry/group cycle lama sebagai active; history tetap tersedia.
6. Replay/lostACK/race tidak double payout; production state tetap terpisah.

Tidak ada source/NRO baru pada v108 karena kontrak request tidak berubah dan
temuan berada di state server. NRO v107 tetap candidate terbaru; tidak perlu
rebuild untuk menguji perbaikan server melalui API yang sama. Hardware Switch
dan bukti DB/grants/load tidak diuji pada retest HTTP ini.

## Retest v107 — ONLINEDEV/CDK deployed, pipeline clock masih terblokir

Riwayat sebelum perbaikan: blocker BOT/fixture/payout di bagian ini sudah
ditutup sebagian pada v108 di atas; gunakan daftar temuan v108 untuk pekerjaan
backend berikutnya, bukan mengulang implementasi yang sudah lolos.

28 Oktober 2026 WIB. Tes HTTP langsung memakai akun DEV yang disediakan operator
dan akun QA produksi yang sudah ada. Tidak membuat akun baru. Snapshot OpenAPI
sekarang45 operasi, SHA256
`3bf97f0ec384d8ef4d40042c5859e5072bd9e2c6e1c77887c2efcd53c644ce61`.
Empat route baru sudah ada; keberadaan route/status200 **belum** membuktikan
pipeline liga selesai. Bukti privat di ignored
`local-debug/manager-backend-retest-v107/`; jangan kirim PIN/token/CDK mentah.

**P1 — clock TEST mengembalikan SUCCEEDED, tetapi liga tidak diproses.**
Ini pekerjaan backend yang masih wajib sebelum demo prep→match→reward dapat
dianggap berfungsi pada Switch. Tidak diselesaikan dengan perubahan jam/phase,
BOT, skor atau hadiah lokal pada client.

| Langkah nyata di TEST | Hasil HTTP dan domain |
| --- | --- |
| Login DEV |200 TEST, demo_time=true, promotion_codes=true, revision2; initial wallet10000/version2 (akun sudah pernah mendapat CDK pada tes operator) |
| Initial time | Selasa27 Oktober00:00 WIB, status W1 REGISTRATION; bootstrap.league=null, league/status cycle1 terbuka |
| Join W1 |201, entry1, +1500 sekali; wallet11500/version3,1 HUMAN0BOT |
| NEXT_MILESTONE base revision2 |200 SUCCEEDED revision3, Rabu28 Oktober12:00 WIB; liga masih REGISTRATION,1 HUMAN0BOT, schedule kosong |
| Replay key/body dan lookup |200, revision tetap3 dan waktu sama; tidak advance kedua kali |
| Stale base revision2, key baru |409 REVISION_CONFLICT |
| NEXT_MILESTONE base revision3 |200 SUCCEEDED revision4, Rabu12:11 WIB; liga masih REGISTRATION, tanpa BOT/fixture |
| FINISH_WEEK base revision4 |200 SUCCEEDED revision5, Minggu1 November09:00 WIB; liga tetap W1 REGISTRATION,1 HUMAN0BOT, schedule/standings/champions kosong |
| Read ulang beberapa menit sesudahnya | State tetap sama; tidak ada match atau podium payout. Wallet hanya berubah oleh bonus join/CDK yang memang diuji |

Repro pada environment TEST saja: login → POST /league/join saat status server
REGISTRATION → advance NEXT_MILESTONE dengan revision terkini hingga kickoff/
fulltime → FINISH_WEEK → GET bootstrap/status/schedule/standings/champions.
SUCCEEDED seharusnya berarti close/autofill/snapshot/compute/seal/publish/
settlement yang relevan telah committed. Dengan1 manusia, group harus menjadi
4 entry (3 BOT),6 fixture/3 round; mencapai Minggu tidak boleh masih registration
dari W1. Pada Selasa registration juga masih menerima join; audit cutoff memakai
clock domain TEST, bukan clock produksi/OS atau status seed statis.

Request IDs bukti: join `req_a4c7bce525b1be23`, step1
`req_8dd6f36aaf4fc160`, step2 `req_10a835a78410e95a`, FINISH_WEEK
`req_f824fb2a31b2b76a`, snapshot akhir `req_7a38d8c4addfa8ce`.
Gunakan revision/waktu terbaru pada tes ulang; jangan hardcode revision2 pada
database yang sudah maju. Tidak perlu reset/drop data production.

Perbaikan backend:

- Bind testWorker/repository/job clock ke realm TEST dan virtual clock domain
  untuk close/cutoff/kickoff/publication/settlement. Verifikasi worker benar-benar
  dijalankan; dari HTTP saja penyebab internal belum dapat dipastikan.
- Jalankan pipeline sampai target dengan durable checkpoints; handler yang baru
  mengubah anchor tidak boleh menandai SUCCEEDED. Gunakan202 RUNNING + lookup
  sampai pekerjaan selesai, atau FAILED dengan checkpoint/error nyata.
- Pastikan NEXT_MILESTONE tidak melewati preparation/registration close yang
  belum diproses, dan FINISH_WEEK menguras pekerjaan jatuh tempo hingga Minggu.
- Tambahkan acceptance yang memeriksa group/BOT/fixture/score/ledger/honours,
  bukan hanya status200, clock_revision atau test_now_ms. Tes operator yang
  dikirim sebelumnya belum memeriksa invariant ini.
- Meta pada response clock saat ini memuat server_now_ms sebelum advance,
  sedangkan data.test_now_ms sudah target. Sebaiknya meta merefleksikan clock
  committed final; client v107 sudah memakai receipt target lalu bootstrap baru.

### Yang lolos retest langsung v107

- Login DEV otomatis TEST dan login QA otomatis PRODUCTION. Dua arah assertion
  header yang berlawanan mendapat403 ENVIRONMENT_MISMATCH pada bootstrap.
  Ini bukti HTTP; isolasi physical DB/grants/secret/worker belum diaudit dari host.
- Satu **CDK TEST** valid mendapat200, redemption2, credit tepat5000:
  wallet11500/version3 →16500/version4. Same-key replay, new-key same-code replay
  dan lookup memakai redemption yang sama; wallet/version tidak bertambah lagi.
- New-key replay mengembalikan idempotency_key request baru, sesuai consumer;
  receipt amount/currency/environment/account/wallet cocok. Tidak mint kode atau
  redeem kode production pada akun nyata.
- Kode TEST dicoba di PRODUCTION mendapat422 INVALID_CODE. Invalid synthetic
  code di TEST juga422 INVALID_CODE. Wallet QA produksi tetap2500/version6,
  collection26, squad/plan sama, pendingnull setelah seluruh clock/CDK TEST.
- Seluruh read bootstrap/profile/collection/squad/plan/offers/pending/status/
  schedule/standings/ranking/champions/news yang dicoba pada kedua realm200.
- 18/18 starter DEV mempunyai canonical player_key/OVR/position yang cocok dengan
  SQLite yang diserahkan; OVR63–68,18 key unik. Ini audit roster akun yang sudah
  dibuat operator, bukan tes fresh-registration baru.
- Stale revision409, same-key clock replay dan durable lookup200. Tidak ada
  clock mutation production, brute force PIN atau akun tambahan.

### Client v107 dan batas verifikasi

Source Switch mendukung auto ONLINEDEV, Demo Time, promotion input dan durable
recovery. Tambahan setelah membaca payload deployment:

- Bootstrap belum join boleh league=null: ambil /league/status sebelum memberi
  status registration/cycle atau membuka Join TEST; jangan menciptakan window lokal.
- Raw frame chunk adalah array tanpa meta; decoder TEST mengizinkannya hanya
  untuk success J_CHUNK yang sudah diotorisasi transport. Header/events/error
  tetap memerlukan realm; error lintas realm tidak boleh menghapus CDK journal.
- Client tidak mengisi fixture/BOT/hadiah sendiri untuk menyamarkan P1 backend.
  Setelah server memperbaiki pipeline, NRO ini dapat fetch domain state yang benar.

Build NRO v107 berhasil memakai native devkitPro Makefile sebagai fallback
setelah build-wsl.ps1 gagal membuka WSL/systemd scope. Source dan paired inputs
dipertahankan, O3/LTO1. Build ID `ae25d88650f6cf5484f240ea2985575e305bdcbf`,
NRO SHA256 `315c1be0352e46c522e4c83835686b8173efaea607ad8cc364afaa1183d43986`.
Tidak di-install otomatis ke runtime/SD dan belum diuji hardware.

28 tes async host client mencakup4 regresi baru untuk null-league/status,
TEST raw chunk dan realm error. Payload deployment juga diperiksa melalui parser
C yang sama. Build/receipt dan hardware acceptance dicatat pada dokumentasi
client/delivery; hasil host bukan bukti bermain pada perangkat Switch.

OpenAPI masih perlu typed response schemas untuk context realm/capabilities/
test_clock dan empat route baru (saat ini hanya description pada response).
Uji LIVE TEST dua viewer dan payout pipeline **belum lulus**, karena tidak ada
fixture TEST yang dibuat. Rekaman production v105 dan bukti lama tetap di bawah.

## Tambahan kebutuhan v106: akun ONLINEDEV dan CDK

Bagian v106 berikut adalah riwayat kontrak sebelum deploy. Status aktual ada di
retest v107 di atas; jangan mengerjakan ulang endpoint/CDK yang sudah terbukti.

28 Oktober 2026. **Implementasi baru untuk agent backend**, terpisah dari temuan
v104 yang sudah selesai pada retest v105 di bawah. Spesifikasi lengkap API,
payload, MySQL migrations, Docker isolation, idempotency dan acceptance:
[ONLINEDEV per akun + promotion CDK v106](MANAGER_ONLINEDEV_CDK_V106.md).

OpenAPI diperiksa ulang pada v106: masih41 operasi, SHA256 sama
`a5449e2f672f55dee5baad687b527f22a2044ead8b58385d9ac2b8c41a07cbc9`.
Belum mendokumentasikan environment/capabilities auth, TEST clock atau promotion
redeem. Tidak mengirim clock mutation/mint/redeem ke deployment yang belum
mengumumkan dukungan itu. Perubahan v106 tidak membatalkan hasil retest v105.

Pekerjaan backend yang harus diselesaikan sebelum enable:

| Area | Kontrak wajib |
| --- | --- |
| Satu User ID DEV | Provision operator, reserved ID, PIN aman; login biasa otomatis TEST berdasarkan account registry server. Client tidak mempunyai bypass berdasarkan nama DEV |
| TEST / PRODUCTION | Dua DB/schema-state terpisah dalam satu MySQL, credentials/grants/worker/cache/blob/jobs terpisah; account/token mengikat realm immutable. Header hanya assertion |
| Auth / bootstrap | data.environment, capabilities.demo_time/promotion_codes, TEST test_clock.revision; setiap envelope meta.environment + clock domain; access expiry/throttle/lease tetap real-time |
| Demo time | POST /dev/clock/advance dengan NEXT_MILESTONE atau FINISH_WEEK + expected_revision, Idempotency-Key; TEST_OPERATOR saja; async202 + GET /dev/clock/operations/{key} |
| Kalender nyata TEST | Pipeline domain yang sama untuk prep, BOT fill-to4, snapshot/compute/seal, LIVE/publication, Sunday5000/4000/3000 dan RP reset; tidak set-score/set-cash atau clock production |
| Promotion / CDK | POST /promotions/redeem {code}, tepat5000 NX Cash per kode sekali pakai; GET /promotions/operations/{key}; unique redemption+ledger source, durable receipt, concurrent/lostACK/restart aman |
| Kode sebelum update | Kode yang sudah aktif boleh diredeem client versi online yang masih diterima; tidak memerlukan future NRO. TEST tidak menghabiskan kode production |
| OpenAPI / bukti | Typed schema empat route baru + context auth/bootstrap/meta, migrations+grants+Go/MySQL tests, kemudian acceptance Switch dengan akun DEV |

Client Switch **source** sudah ditambahkan consumer kontrak ini: auto ONLINEDEV
dari response server, Y Demo Time di hub TEST, Join TEST saat registration,
konfirmasi/async loading/poll/recovery, Shop X Promotion Code, keyboard, popup
dan wallet receipt/bootstrap. Unknown status memakai journal/key/body yang sama;
tidak menambah cash atau menggeser jam lokal untuk berpura-pura online.
PRODUCTION tidak mendapat kontrol clock, dan offline DEV tetap tersendiri.
24 tes async host lulus (10 regresi+14 baru); ini tes synthetic, **bukan** bukti
endpoint baru tersedia atau hardware Switch lulus. Sessionv1 memerlukan login
ulang; sessionv2 mengikat realm, journal clock/CDK terpisah realm+account+origin.

Backend owner perlu menyediakan akun DEV dan capability/endpoint tersebut;
username/PIN/mint export dikirim privat, tidak di-commit ke review ini. Tidak
membuat akun kedua atau mengubah realm akun QA yang sudah ada secara otomatis.

## Bukti retest deployment v105 (dipertahankan)

Retest **v105**, 28 Oktober 2026 mulai **20:37 WIB**. Backend mengumumkan online
`1.0.0`, API schema `1`. Target tetap Go + MySQL + Docker, Ubuntu 2 CPU / 2 GB.
API: `https://wedreamku.my.id/footballnx/api/v1`.
[OpenAPI deployment](https://wedreamku.my.id/footballnx/openapi.yaml).
Aturan produk: [BACKEND-PLAN / handoff v1](MANAGER_BACKEND_HANDOFF_V1.md).

**Ketiga temuan utama v104 sudah tertutup pada tes ini:** metadata/taktik invalid
ditolak, schedule dan recording konsisten, serta halftime dapat dibaca melewati
seluruh22 chunk. Tes regresi yang dijalankan juga lolos. Tidak ada P0/P1 baru
yang direproduksi dalam lingkup retest ini; integrasi client dapat dilanjutkan.
Ini bukan klaim seluruh fitur backend, production load atau Switch sudah lulus.

Bagian retest ini menggantikan review v104. Jangan mengerjakan ulang temuan lama yang
di bawah sudah ditandai selesai. Bukti mentah dan snapshot sebelumnya disimpan
lokal pada ignored `local-debug/manager-backend-retest-v105/`.

## Lingkup dan keadaan akhir QA

Memakai akun QA yang sama. Tidak membuat akun tambahan, membeli pack baru,
mengubah akun lain, menggeser clock server, mengakses database atau melakukan
brute force PIN. Payment/grant regression memakai key dan body transaksi QA
sebelumnya, sehingga hanya menguji replay receipt yang sudah ada.

- Wallet tetap **2.500 NX Cash/version6**, collection tetap **26** canonical keys
  unik, pending pack akhir kosong. Tidak ada debit/grant baru pada retest ini.
- Squad tetap18 ID semula. Game Plan valid revision17 → 18 pada Save normal,
  lalu revision19 pada satu pemenang Save konkuren; kontennya tetap legal.
- Sepuluh probe plan invalid ditolak tanpa perubahan state/revision. Satu Save
  valid mendapat200 dan GET cocok; tidak perlu pemulihan plan invalid.
- Tidak ada perubahan source client atau build NRO baru pada retest v105.
- PIN, token, recovery code dan file sesi tidak boleh dipublikasikan.

OpenAPI snapshot: **27.768 byte, 41 operasi, 2 media success response berschema**.
SHA256 `a5449e2f672f55dee5baad687b527f22a2044ead8b58385d9ac2b8c41a07cbc9`.

## Temuan v104 yang selesai

| Temuan | Bukti v105 |
| --- | --- |
| player_key palsu pada owned instance | 422 INVALID_PLAYER_KEY; plan/revision tetap |
| tactics.tempo tidak dikenal | 422 INVALID_TACTIC_ENUM; plan/revision tetap |
| Schedule SCHEDULED tetapi header ENDED | Semua6 fixture sekarang mempunyai state dan kickoff/broadcast time yang sama di kedua endpoint |
| W2 dijadwalkan Kamis | Lima fixture SCHEDULED sekarang Sabtu31 Oktober, 12:00/12:45/13:30 WIB; satu fixture QA yang sudah ENDED memakai broadcast Rabu yang sama di schedule/header |
| Halftime chunk10/11 JSON null | Keduanya array frame valid;22/22 chunk lolos parser C client |
| Schema score null salah | Schedule dan standings sekarang lulus JSON Schema2020-12 pada payload aktual,0errors |
| Expected revision opsional pada plan schema | Sekarang required; enums formation/tactics juga ditulis eksplisit |

Request IDs: forged key `req_f0003970bf9711e4`, invalid tactic
`req_51138757df5ffdb9`, recording29 header `req_3b7cd3acf476086f`, schedule
`req_61c65654267d8a57`. Chunk gzip tidak memakai envelope request_id;
endpoint dan payload bukti tersimpan sebagai `matches-29-chunk-0..21.json`.

## Regresi Game Plan dan fondasi Save-on-leave

| Kasus | Hasil |
| --- | --- |
| Missing expected_revision | 400 MISSING_EXPECTED_REVISION, tidak berubah |
| Stale expected_revision | 409 REVISION_CONFLICT, tidak berubah |
| XI instance duplikat | 422 DUPLICATE_PLAYER_IN_XI, tidak berubah |
| Instance tidak dimiliki QA | 403 PLAYER_NOT_OWNED, tidak berubah |
| x105001 melebihi pitch | 422 INVALID_COORDINATES, tidak berubah |
| Dua natural GK di XI | 422 INVALID_XI_ROSTER, tidak berubah |
| Captain bukan XI | 422 INVALID_CAPTAIN, tidak berubah |
| XI kurang dari11 | 422 INVALID_XI_COUNT, tidak berubah |
| Forged canonical key | 422 INVALID_PLAYER_KEY, tidak berubah |
| Enum tempo invalid | 422 INVALID_TACTIC_ENUM, tidak berubah |
| Seluruh plan valid | 200, revision17 → 18, konten GET cocok |
| Replay key/body Save sama | 200, response data identik, tidak menaikkan revision |
| Dua Save berbeda key/base revision sama | Satu200/satu409, revision18 → 19 hanya sekali |

Save normal `req_ccd7af88d72b07c6`; replay `req_7e22743f48bb4ab3`;
concurrent winner `req_985c27870fadb242`, conflict `req_fce0d82690e8b1d3`.
Response Save memuat revision dan content_hash. Control expected_revision tidak
lagi berada di dalam plan snapshot yang tersimpan.

Kontrak editor tetap: perubahan menjadi **draft lokal**, tidak PUT setiap edit.
Leave clean0PUT; leave dirty1full-plan PUT dengan revision/roster asal, intent/key
tersimpan dan loading single-flight. Submenu formasi/posisi bukan leave editor.
ACK sukses baru membersihkan dirty; timeout/lost ACK memakai replay atau GET
untuk reconcile. Konflik tidak membuang draft atau otomatis overwrite revision
perangkat lain. Draft terpisah per account/origin dan bisa dipulihkan saat app
dibuka kembali, setelah memeriksa revision/cutoff.

**Fondasi backend untuk pola ini lolos**, tetapi editor online client belum
diaktifkan. UX Save saat keluar halaman belum dites pada Switch; jangan mengaku
fitur itu sudah terpasang hanya berdasarkan tes HTTP. DEV offline tetap memakai
storage/clock terpisah dan harus mengikuti semantik draft/commit yang sama.

## Konsistensi jadwal, skor dan BOT

Pada6 fixture grup QA:

- State dan timestamp kickoff/broadcast cocok antara schedule dan header.
- Fixture29 ENDED di keduanya, kickoff1793189774633 = Rabu28 Oktober
  19:16:14.633 WIB; score0–0 tersedia dan report/chunks dapat dibaca.
- Lima fixture lain SCHEDULED dengan waktu Sabtu31 Oktober12:00/12:45/13:30 WIB;
  score null, header watermark0, report/chunk belum terbuka. Tidak lagi Kamis.
- Group mempunyai4 entry,3 HUMAN +1 BOT,6 pasangan unik dan3 round. Tidak ada
  tim bermain dua kali dalam satu round; home/away delta maksimal1.
- Status minimum_entries4, remaining_needed0. Stable entry/club/presentation IDs,
  nama, league_points dan BOT flag tetap tersedia.

Ini memverifikasi state deployment yang tersedia, **bukan** membuktikan seluruh
registration-close scheduler, H0/1/2 autofill, carry migration atau Sunday payout.
Fixture29 adalah sampel QA yang broadcast waktunya sudah dipindah pada pengujian
sebelumnya; jangan menjadikannya contoh kalender production normal.

Aturan produk tetap H0 tutup kosong; H1/2/3 isi BOT3/2/1 hingga4 saat close;
H>=4 tanpa BOT tambahan, grup4–16. Tidak carry karena kurang peserta. Entry
legacy dipertahankan tanpa bonus ganda. BOT tanpa login/wallet/bonus/cash/RP akun;
rank campuran tetap resmi dan honours BOT berlabel. Aturan lengkap tetap §7 plan.

## Rekaman dan seluruh chunk halftime

Fixture29 mengumumkan recording_version1 dengan hash baru:
`5493452528ac1109c7ed5e52aab4ed5387586b8e8ca554cd545d9724a24b27e5`.
Hash v104 sebelumnya3750694a418bf3df136959e953dbfc79b3e24e74d1f42f9f29cbc83a83b388e2.
Jadi ini sampel QA yang telah diregenerasi, bukan tape lama yang tetap identik.
Untuk arsip production, pertahankan kebijakan recording/version/hash immutable
dan jelaskan migrasi/release generator; lifecycle itu belum diaudit dari HTTP.

Hasil pembacaan22 chunk, duration660000 ms:

- Seluruh respons200 gzip berisi **array**, tanpa null chunk.
- Total659 frame, at_ms0 sampai659000, waktu monoton. Kedua chunk halftime
  dapat dibaca dan **22/22 chunk diterima parser C**, termasuk transisi babak.
- Sebelas actor per sisi pada setiap frame, tidak ada koordinat keluar pitch.
- Posisi dua dimensi bergerak; frame kickoff awal tidak menaruh pemain di half
  lawan. Jarak bc ke bola pada sampel sekarang0, membaik dari mismatch v104.
- Events470: PASS433, SAVE33, KICKOFF2, HALF_TIME1, FULL_TIME1. Sekarang ada
  actor_instance_id pada468 event dan recipient_instance_id pada435 event.

Ini membuktikan tipe/koordinat/frame decoding dan perbaikan sampel, bukan
penilaian visual penuh animasi atau validasi seluruh hukum sepak bola. Tidak ada
pertandingan LIVE tersedia untuk tes dua viewer saat retest. Backend tetap perlu
golden corpus dengan input snapshot/strength, event-report reconciliation,
outcomes dan actor/lineup bindings historis untuk touchline/commentary lengkap.
Satu hasil0–0 bukan bukti simulator salah maupun bukti balancing selesai.

Catatan kualitas data yang masih perlu definisi/reconciliation: report memuat
completed passes236/230, sementara event PASS220/213 per sisi. Jelaskan apakah
satu event merepresentasikan beberapa pass, atau selaraskan reducer report
dengan event log. Perbedaan sampel ini belum dianggap selesai pada retest v105.

## Transaksi, versi dan catalog

Regresi finansial kali ini hanya replay transaksi yang sudah di-grant:
dua POST pay bersamaan dengan key/body lama mendapat201 dan receipt data sama;
grant replay200, lookup pay/grant200. Wallet/version dan26 owned instances tidak
berubah. Tidak membeli pack atau menguji ulang selection pada pending baru;
uji missing/stale/duplicate selection dari v104 tetap bukti sebelumnya, bukan
diklaim dijalankan ulang pada v105.

26/26 owned canonical keys, OVR dan position tetap cocok dengan SQLite, tidak
ada duplicate key. Old/missing online version426, wrong catalog409 tetap bekerja.
Catalog manifest394 tim/10.433 pemain dan runtime pair e861c583ec78e9ae cocok.
Logical hash:
`2ffab2858daa681400e89445d75c28c0d8ac951bd36b0ec4af35ff08020f1222`.
SQLite SHA256:
`1678985ae3ee1e16da193fdd7356768bc690ac40a8a2f62fad11bfd8d0f8a826`.

## Verifikasi client dan langkah berikutnya

- **10 tes async host client passed**, source client tidak berubah pada v105.
- **14 payload positif** diterima parser C: delapan payload inti, schedule dan
  standings secara semantik, header/chunk0/halftime10/11 rekaman29.
- Satu probe tambahan SCHEDULED header sengaja ditolak parser watch LIVE/ENDED.
  Ini **expected rejection**, bukan kegagalan API baru: UI schedule memang
  menampilkan popup belum mulai dan tidak membuka watch untuk phase SCHEDULED.
- Audit terpisah semua22 chunk rekaman29: **22/22 PASS**, bukan hanya chunk0.
- Schedule/standings masing-masing0 error terhadap schema respons yang sekarang
  terpasang. Hanya2 dari41 operasi mempunyai typed success schema; lengkapi
  operasi lain sebagai pekerjaan dokumentasi/contract coverage lanjutan.
- Tidak ada source client baru, NRO baru atau tes hardware pada retest ini.

Lanjutkan integrasi client berdasarkan kontrak yang sudah lulus ini: editor
draft/Save-on-leave, recovery operation lookup, actor/name presentation dan
submenu yang belum terhubung. NRO v101 lama belum otomatis mempunyai perubahan
source minimum4 dari retest sebelumnya; perlu build client berikutnya.

Verifikasi di luar lingkup yang masih harus mempunyai bukti backend/acceptance:
fresh starter registration, cross-account authorization, autofill close yang
idempoten, Sunday settlement/RP14 hari/honours, LIVE dua-viewer/reconnect/spoiler,
MySQL driver/migration/image, resource Go+DB pada2 CPU/2 GB, serta auth/recovery/
rate limits dan durable receipt retention. Tidak dilakukan admin clock, DB access
atau brute force production untuk menyelesaikan pemeriksaan tersebut.
