# Manager League hub v111 — UI dan kontrak backend

**Revisi lanjutan:** [v112](MANAGER_HUB_V112.md) menggantikan layout tab LEAGUE
dengan empat tile, menambahkan ranking bulanan (menggantikan reset 14 hari),
badge LIVE, dan penyempurnaan label/spacing. Kontrak fase dan feed di bawah
tetap berlaku kecuali bagian yang secara eksplisit diganti v112.

29 Oktober 2026. Revisi produk ini berlaku untuk ONLINE/ONLINEDEV. DEV OFFLINE
memakai susunan menu yang sama dengan data lokal untuk pengembangan. Ini bukan
laporan bahwa endpoint baru sudah dideploy atau lolos tes pada Switch.

## Susunan dan tindakan

| Tab | Posisi | Menu | Tindakan A |
| --- | --- | --- | --- |
| HOME | Atas kiri | Registration Day W1/W2, Preparation Day, Match Day, League End | Sesuai fase di bawah |
| HOME | Atas kanan | Club Feed | Satu kolom kartu aktivitas besar |
| HOME | Bawah kiri | Schedule | Tujuh tile dalam satu kolom, Senin–Minggu |
| HOME | Bawah tengah | League Standings | Popup selama Registration; tabel mulai Preparation |
| HOME | Bawah kanan | Club Profile | Profil existing: identitas, atlas, statistik dan submenu |
| MY TEAM | Atas kiri | Game Plan | Editor formasi, XI, taktik; simpan ketika meninggalkan halaman |
| MY TEAM | Atas kanan | Player Feed | Top Scorers dan Rising Stars; hanya Match Day sampai League End |
| MY TEAM | Bawah kiri | Shop | Pack dan Promotion Code existing |
| MY TEAM | Bawah tengah | Other Team Profile | Daftar klub, lalu profil/squad/Game Plan/history lawan |
| MY TEAM | Bawah kanan | Trade History · Upcoming | Popup informasi, OK saja; tidak mengirim transaksi |
| LEAGUE | Atas kiri | League Champion | Riwayat juara liga terdahulu, tidak terhapus oleh reset ranking |
| LEAGUE | Atas kanan | League Guide & Rules | Jadwal per hari, poin, bonus, hadiah dan reset Overall Rank |
| LEAGUE | Bawah | Logout | Konfirmasi logout existing |

Registered Squad, Collection, Overall Rank, Match History dan League Rewards
tetap tersedia melalui Club Profile. Menghapus tile duplikat tidak menghapus
fitur atau data tersebut. Tombol X tidak lagi menjadi shortcut Logout di hub.
Y tetap Demo Time pada ONLINEDEV/DEV OFFLINE atau Refresh untuk online biasa.

### Tile fase: countdown dan status pendaftaran

Tile selalu memisahkan **judul fase**, **`ENDS IN 20H 14M`**, dan status
**`REGISTERED` / `NOT REGISTERED`**. Status belum diketahui harus dinyatakan
pending, bukan mengaku belum ikut. Konfirmasi menggunakan default Cancel.

- Registration, belum terdaftar: A → konfirmasi REGISTER/Cancel. Hanya menerima
  konfirmasi yang mengirim `POST /league/join`. Bonus tepat +1.500 NX Cash sekali.
- Registration, sudah terdaftar: A → penjelasan Registration, OK saja.
- Preparation: A → penjelasan persiapan, OK saja.
- Match Day atau League End: A → Match Centre existing, tiga bagian LIVE,
  SCHEDULED, MATCH ENDED. Countdown tetap terlihat pada tile hub.
- Menutup popup dengan A tidak boleh sekaligus mengaktifkan tile di bawahnya.
- Jika tenggat lewat saat popup konfirmasi terbuka, refresh status; jangan
  mengirim join ke jendela berikutnya tanpa persetujuan baru.

Countdown berdasarkan `meta.server_now_ms` ditambah waktu monotonic sejak
respons. Di TEST gunakan domain virtual clock yang sama dengan seluruh endpoint
liga. Kalender UI menggunakan WIB, bukan zona waktu perangkat. Jangan memaksa
fase baru hanya karena timer lokal habis: server tetap memutuskan fase/admission.
Field waktu tidak tersedia → `TIME TO BE CONFIRMED`; tenggat lewat → refresh
status. Jangan membuat timer palsu atau memberi bonus dari timer client.

## Status liga dan kalender

Tambahkan pada object `league` di `GET /me/bootstrap` dan pada `GET /league/status`:

```json
{
  "cycle_id": 15,
  "label": "W1",
  "state": "REGISTRATION",
  "user_joined": false,
  "waiting_entry_count": 1,
  "minimum_entries": 4,
  "remaining_needed": 3,
  "phase_started_at_ms": 1793552400000,
  "phase_ends_at_ms": 1793638800000,
  "registration_open_ms": 1793552400000,
  "registration_close_ms": 1793638800000,
  "first_kickoff_ms": 1793768400000,
  "last_full_time_ms": 1793776260000,
  "rewards_at_ms": 1794114000000,
  "next_registration_at_ms": 1793811600000
}
```

Contoh timestamp ilustratif, bukan fixture produksi. Semua epoch-ms integer
UTC. Identitas cycle, state, membership dan jadwal harus merujuk window yang
sama; perbaikan stale cycle pada review v110 tetap wajib. Jangan mencari row
REGISTRATION lama atau menyamakan account_id, club_id dan presentation_team_id.

| Hari WIB | Window | Fase/isi tile Schedule |
| --- | --- | --- |
| Senin | W1 | Registration & preparation; tutup Selasa 00:00 |
| Selasa | W1 | Preparation, finalisasi Game Plan |
| Rabu | W1 | Match Day; setelah fixture terakhir menjadi League End |
| Kamis | W2 | Registration & preparation; tutup Jumat 00:00 |
| Jumat | W2 | Preparation, finalisasi Game Plan |
| Sabtu | W2 | Match Day; setelah fixture terakhir menjadi League End |
| Minggu | W1 + W2 | Results overview dan pembagian hadiah kedua liga |

Semantik fase: Registration berakhir tengah malam, Preparation berakhir awal
hari pertandingan (00:00 WIB), Match Day berakhir pada full time terakhir,
League End berakhir saat Registration berikutnya dibuka. Sunday overview memakai
League End W2; settlement terpisah dari akhir pertandingan. Tidak ada liga kosong:
1–3 manusia diisi BOT menjadi empat, nol manusia tidak perlu dibuatkan grup.

Schedule adalah kalender **minggu nyata yang sedang berjalan**, bukan daftar
fixture. Client dapat membentuk tujuh tanggal dari server_now dan aturan WIB;
tidak diperlukan endpoint kalender duplikat. Hari ini diberi latar biru muda dan
label TODAY. Fokus controller terpisah dari penanda TODAY. Setiap tile memuat
tanggal lengkap, W1/W2, dan satu deskripsi. Tidak ada aksi membuka pertandingan
pada tile kalender; pertandingan dibuka lewat tile fase atau Match History.

Sediakan `phase_ends_at_ms` walaupun belum ada tim atau fixture. Fallback client
untuk backend lama adalah waktu penutupan/pertandingan/pendaftaran berikut yang
sudah tersedia; tanpa field itu tampil waktu belum terkonfirmasi.

## Club Feed: GET /api/v1/news

Pertahankan URL dan envelope authentication/environment existing. Payload baru:

```json
{
  "data": {
    "items": [
      {
        "event_id": "signing:901:ef:1001",
        "type": "PLAYER_SIGNED",
        "cycle_id": 15,
        "league_label": "W1",
        "occurred_at_ms": 1793592000000,
        "parameters": {
          "club_id": 84,
          "club_name": "Example FC",
          "presentation_team_id": 108,
          "player_key": "ef:1001",
          "player_name": "Example Player"
        }
      },
      {
        "event_id": "result:55",
        "type": "MATCH_RESULT",
        "cycle_id": 15,
        "league_label": "W1",
        "occurred_at_ms": 1793769060000,
        "parameters": {
          "fixture_id": 55,
          "home_club_id": 84,
          "away_club_id": 31,
          "home_club_name": "Example FC",
          "away_club_name": "Rival FC",
          "home_presentation_team_id": 108,
          "away_presentation_team_id": 101,
          "home_goals": 2,
          "away_goals": 1
        }
      },
      {
        "event_id": "leader:15:round-1",
        "type": "LEAGUE_LEADER",
        "cycle_id": 15,
        "league_label": "W1",
        "occurred_at_ms": 1793769060000,
        "parameters": {
          "club_id": 84,
          "club_name": "Example FC",
          "presentation_team_id": 108,
          "league_points": 3
        }
      }
    ]
  },
  "meta": { "environment": "TEST", "server_now_ms": 1793769100000 }
}
```

Meta contoh disingkat; tetap kirim seluruh field versi/request_id yang diwajibkan
kontrak existing. Client menerima array legacy maupun object `items`. `null` atau
`items:[]` adalah keadaan kosong yang sah.

- Urut newest first, tie event_id stabil. Maksimal 256 aktivitas terbaru dalam
  minggu nyata berjalan, scoped ke grup liga yang diikuti user pada W1/W2; sebelum
  grup terbentuk, tampilkan aktivitas klub sendiri saja. Ini ringkasan aktivitas,
  bukan ledger transaksi lengkap. Client menampilkan tiga kartu besar per layar;
  analog L scroll, L/R halaman. Tidak ada transfer fiktif atau skor default 0–0.
- Emit PLAYER_SIGNED **setelah grant pemain**, bukan setelah pay atau memilih
  pool. Satu event per pemain yang benar-benar didapat. Idempoten terhadap retry
  grant: unique `(purchase_id, player_key)`.
- MATCH_RESULT baru terbit sesudah waktu full time. Precomputed tape tidak boleh
  bocor ke feed sebelum tayang selesai. Unique fixture_id.
- LEAGUE_LEADER berdasarkan tabel resmi sesudah satu round selesai, termasuk
  tiebreak. Event menyebut posisi saat itu; jangan menyebut setiap event lama
  sebagai pemuncak saat ini. Unique `(group_id, round_number)`.
- Nama disimpan sebagai snapshot UTF-8. `player_key` tetap canonical katalog;
  `presentation_team_id` adalah ID atlas lokal. Jangan mengirim URL aset atau
  mewariskan portrait berdasarkan reused native slot.

Rekomendasi MySQL: `league_activity(id, event_key UNIQUE, cycle_id, group_id NULL,
club_id NULL, type, occurred_at_ms BIGINT, parameters JSON)`, index
`(group_id, occurred_at_ms, id)` dan `(club_id, occurred_at_ms, id)`. Simpan outbox
dalam transaksi yang sama dengan grant/publikasi hasil, lalu upsert event_key.
Jangan generate ulang aktivitas setiap GET. Database TEST dan PRODUCTION tetap
terpisah. Backfill dari receipt/result resmi saja, tanpa nama/skor buatan.

## Player Feed: GET /api/v1/league/player-feed

Tambahkan `capabilities.player_feed_v1: true` pada bootstrap **hanya setelah
endpoint siap**. Client lama tetap berjalan tanpa flag; client v111 menampilkan
popup data belum tersedia tanpa melakukan request endpoint yang belum ada.

```json
{
  "data": {
    "cycle_id": 15,
    "published_through_ms": 1793769060000,
    "top_scorers": [
      {
        "player_key": "ef:1001",
        "player_name": "Example Player",
        "club_id": 84,
        "club_name": "Example FC",
        "presentation_team_id": 108,
        "snapshot_ovr": 68,
        "goals": 2,
        "assists": 1
      }
    ],
    "rising_stars": [
      {
        "player_key": "ef:1001",
        "player_name": "Example Player",
        "club_id": 84,
        "club_name": "Example FC",
        "presentation_team_id": 108,
        "snapshot_ovr": 68,
        "goals": 2,
        "assists": 1
      }
    ]
  },
  "meta": { "environment": "TEST", "server_now_ms": 1793769100000 }
}
```

- Hanya fase Match Day/League End, grup liga user dan cycle berjalan. Sebelum
  Match Day: 409 `PLAYER_FEED_NOT_AVAILABLE`. Belum ikut/grup belum ada: 409
  `LEAGUE_NOT_JOINED`. Sudah masuk fase tetapi belum ada gol: HTTP 200, array
  kosong, watermark publikasi valid. Tidak ada entry palsu untuk mengisi layar.
- Maksimal 32 pemain per list, tidak ada duplikat canonical player_key dalam
  list yang sama. Pemain boleh ada di kedua list. Tidak perlu query per pemain.
- Top Scorers: goals > 0; urut goals desc, assists desc, player_key asc.
- Rising Stars pada tahap ini **bukan kategori umur**: snapshot OVR <=69 dan
  setidaknya satu gol/assist; urut `(3*goals + 2*assists)` desc, goals desc,
  player_key asc. Ini definisi produk yang transparan untuk starter ber-OVR 60an;
  tidak mengarang umur yang belum tersedia di katalog client.
- OVR dari snapshot roster yang terkunci sebelum match day. Akumulasi statistik
  berdasarkan player_key, bukan slot XI atau nama. Assist harus dari event resmi;
  jangan menebak dari orang yang paling dekat dengan pencetak gol.
- `published_through_ms <= meta.server_now_ms`. Hanya event yang sudah mencapai
  posisi tayangnya. Perubahan Game Plan setelah kickoff tidak mengubah snapshot.
  Hasil sudah dihitung di backend boleh disimpan penuh, tetapi GET ini tetap
  memfilter publikasi. Jangan melakukan simulasi ulang saat membuka feed.
- MySQL: materialized `league_player_stats(group_id, cycle_id, player_key,
  club_id, snapshot_ovr, goals, assists, published_through_ms)` dengan unique
  `(group_id, player_key)`. Worker update incremental memakai unique
  `(fixture_id, event_sequence)` agar clock/retry tidak menggandakan statistik.
  Cache dua top-32 list per grup setelah publikasi event; cukup ringan untuk VPS
  2 core/2 GB, tidak ada websocket atau rendering 3D baru.

## Admission, compatibility dan acceptance

`POST /league/join` existing tetap memakai Bearer, X-FNX-Environment dan
Idempotency-Key. Unique membership `(cycle_id, account_id)` dan unique ledger
bonus membership adalah perlindungan utama terhadap retry setelah respons hilang,
termasuk UUID baru setelah restart. Saldo client hanya berubah dari bootstrap /
receipt resmi. State/membership yang tidak konsisten tidak boleh menghasilkan
bonus ganda atau join diam-diam ke cycle berikut.

Test backend yang harus ditambahkan:

1. Senin belum join → Cancel tanpa mutation → Confirm → +1.500 tepat sekali →
   bootstrap/status user_joined=true → confirm/retry tidak memberi bonus kedua.
2. Ulangi W2 dan boundary Selasa/Jumat 00:00 WIB. Pendaftaran di fase lain ditolak.
   Uji response lost, refresh token, TEST clock jump, restart dan dua request paralel.
3. Semua fase memiliki start/end konsisten; 1–3 manusia diisi BOT menjadi empat;
   kedua match day, full time, Minggu hadiah, Senin berikutnya punya state benar.
4. Squad grants menghasilkan nama/player_key dan atlas benar, tepat sekali;
   pack baru dibayar tidak membuat event pemain sudah diperoleh.
5. Feed hanya grup/realm berhak, newest first, batas 256, null/empty aman,
   tidak mengandung skor masa depan dari tape lengkap.
6. Top scorer/Rising Star menggunakan event yang telah tayang; skor akhir
   precomputed tidak muncul lebih awal; retry publish dan replay tidak menambah
   statistik. Uji player_key sama dengan slot/nama berbeda dan dua realm.
7. Juara tersimpan permanen ketika Overall Rank reset 14 hari; Trade History
   tidak memerlukan endpoint/mutasi. Production account tidak dapat advance clock.

DEV OFFLINE memakai menu, popup, kalender, feed dan controller yang sama. Liga
baru lokal memakai Rabu/Sabtu; archive lama tidak ditulis ulang. Statistik lokal
dibaca dari event tape yang sudah tayang; tape lama tidak memiliki data assist,
maka preview lokal hanya menampilkan gol. Tidak ada data offline yang diunggah
atau dijadikan hasil resmi liga online.
