# Manager League v112 — ranking bulanan dan penyempurnaan hub

29 Oktober 2026. Kontrak ini melanjutkan [hub v111](MANAGER_HUB_V111.md),
dan menggantikan susunan tab LEAGUE serta aturan Overall Rank lama (reset 14
hari). Implementasi client tersedia untuk ONLINE, ONLINEDEV dan DEV OFFLINE.
Endpoint bulanan di bawah merupakan permintaan backend baru; dokumen ini
tidak menyatakan bahwa deployment sudah mendukungnya.

## Tampilan dan navigasi yang disepakati

| Posisi tab LEAGUE | Tile | Isi |
| --- | --- | --- |
| Atas kiri | League Ranking History | Juara liga W1 dan W2 dari minggu terdahulu |
| Atas kanan | League Ranking | Ranking poin bulanan, dua tab Current Season dan Past Season |
| Bawah kiri | Logout | Konfirmasi logout existing |
| Bawah kanan | League Guide | Aturan hari, poin, pendaftaran dan hadiah |

Analog/D-pad menggerakkan fokus dalam grid 2x2. L/R mengganti tab hub.
League Guide menjadi tile sendiri; tidak ada shortcut X Guide atau X Logout.
HOME dan MY TEAM mengikuti v111; Club Profile dan semua submenunya tetap ada.
Submenu Overall Rank pada profil sekarang membuka League Ranking bulanan.

Tile fase HOME memisahkan judul, countdown, dan status REGISTERED atau NOT
REGISTERED. Hapus teks A TO JOIN/A TO REGISTER. A tetap membuka konfirmasi
pendaftaran saat Registration dan user belum ikut. Setelah ikut, A hanya popup
penjelasan; Preparation juga popup OK. Match Day/League End membuka Match Centre.

Saat Match Day memiliki setidaknya satu siaran LIVE dalam grup liga berjalan,
tile fase menampilkan badge merah LIVE di kanan atas. Tidak terbatas pada match
klub sendiri. Tidak tampil pada Registration, Preparation, League End, saat
semua match masih Scheduled, atau ketika seluruh siaran telah berakhir.
Countdown dan status pendaftaran tetap terlihat.

Club Feed tidak memiliki subtitle “Signings match results…”. Kartu aktivitas
langsung berada di bawah judul. Schedule memakai badge TODAY tersendiri yang
sejajar dengan label League W1/W2; fokus controller tetap berbeda dari TODAY.
Player Feed memisahkan nama pemain, klub dan peringkat dari kolom GOALS,
ASSISTS, MATCH OVR. Hindari baris berisi deretan nilai dengan pemisah `/`.
Poin partisipasi dan masing-masing hadiah podium juga ditampilkan berlabel.

## Tiga jenis poin/saldo

| Jenis | Sumber | Reset |
| --- | --- | --- |
| League Points | Menang 3, seri 1, kalah 0; menentukan klasemen W1/W2 | Liga berikutnya |
| Monthly Ranking PTS | Partisipasi dan posisi akhir liga, tabel di bawah | Setiap bulan kalender WIB |
| NX Cash | Saldo awal, bonus join, podium, CDK, belanja | Tidak direset oleh ranking |

| Peristiwa per liga | Tambahan Monthly Ranking PTS |
| --- | ---: |
| Partisipasi terkonfirmasi | 500 |
| Juara 1 | 2.000 |
| Juara 2 | 1.500 |
| Juara 3 | 1.000 |
| Posisi lain | 0 tambahan podium |

Poin bersifat **kumulatif**: peserta yang juara 1 menerima 500 + 2.000 = 2.500
PTS untuk satu liga. Juara 2 total 2.000, juara 3 total 1.500, peserta lainnya
500. Poin W1 dan W2 dijumlahkan selama bulan yang sama. Tidak ada pengurangan
PTS karena kalah. Hadiah NX Cash tetap: awal 5.000, join +1.500, podium
5.000/4.000/3.000; perubahan ranking tidak mengubah wallet atau harga pack.

Aturan implementasi backend:

1. Identitas pemilik poin adalah account manusia dengan club terikat, bukan
   presentation_team_id. BOT tidak masuk ranking global bulanan. Podium memakai
   posisi liga sebenarnya: BOT di posisi pertama tidak membuat manusia di posisi
   kedua menerima hadiah posisi pertama. Riwayat juara W1/W2 boleh berisi BOT.
2. +500 dicatat dalam transaksi join yang mengesahkan membership. Retry join,
   reconnect, refresh dan clock recovery tidak membuat bonus kedua. Kalau user
   sudah join liga yang sama, kembalikan membership/receipt existing.
3. Poin podium dikredit setelah klasemen akhir resmi dipublikasikan seusai
   siaran terakhir liga, **bukan** ketika skor dihitung sebelum Match Day.
   Settlement NX Cash hari Minggu tetap terpisah.
4. Setiap kredit memiliki effective_at_ms resmi. Bulan partisipasi berasal dari
   waktu join; bulan podium berasal dari final-table publication. Liga lintas
   bulan boleh memiliki dua kredit pada bulan berbeda. Jangan memindahkan +500
   lama ke bulan baru atau mengkredit ulang karena reset.
5. Satu season adalah `[tanggal 1 00:00 WIB, tanggal 1 bulan berikut 00:00 WIB)`.
   Gunakan Asia/Jakarta, bukan 30 hari atau zona perangkat. PRODUCTION memakai
   clock nyata; TEST memakai virtual clock realm, termasuk pergantian tahun.
6. Current Season mencakup semua account manusia yang memiliki kredit pada
   bulan itu, urut points desc, jumlah juara 1 desc, jumlah juara 2 desc,
   jumlah juara 3 desc, club_id asc. Rank berurutan 1 sampai terakhir.
7. Setelah tutup bulan, simpan satu juara pertama sebagai snapshot permanen.
   Past Season berisi satu juara per bulan selesai, terbaru dahulu. Bulan tanpa
   kredit manusia tidak menghasilkan juara fiktif. Nama/atlas saat penutupan
   tetap tersimpan meskipun profil kemudian berganti.

## Kontrak HTTP baru

Semua path di bawah relatif terhadap `/api/v1`. Pertahankan Bearer session,
X-FNX-Environment, version/catalog gate dan envelope meta existing. Respons
harus memuat meta.environment, server_now_ms, real_server_now_ms,
online_version, api_schema_version dan request_id. Contoh berikut hanya `data`.

Aktifkan `capabilities.monthly_ranking_v1: true` dalam bootstrap setelah
migrasi dan endpoint selesai. Tanpa capability, client menampilkan popup bahwa
ranking bulanan belum tersedia. Data RP reset 14 hari tidak dipakai sebagai PTS
bulanan. Tidak diperlukan perubahan kontrak login atau versi katalog pemain.

### GET /ranking/monthly/current

Query wajib: `page=1&page_size=50`. Page selanjutnya menambahkan
`snapshot_id` dari respons pertama.

```json
{
  "period": "CALENDAR_MONTH",
  "scope": "CURRENT",
  "snapshot_id": "test_202611_r84",
  "page": 1,
  "page_size": 50,
  "total": 1,
  "season": {
    "season_id": "2026-11",
    "starts_at_ms": 1793466000000,
    "ends_at_ms": 1796058000000
  },
  "items": [
    {
      "rank": 1,
      "club_id": 84,
      "club_name": "Example FC",
      "presentation_team_id": 108,
      "points": 2500,
      "participation_points": 500,
      "podium_points": 2000
    }
  ]
}
```

Total adalah jumlah seluruh peserta, tidak dibatasi 50/256 tim. Items berisi
tepat min(50, total-offset) baris. Page terakhir boleh kurang dari 50. Ranking
kosong: page 1, total 0, items [], season tetap valid. Nilai points harus sama
dengan participation_points + podium_points, semua integer nonnegatif.
Poin dikirim numerik; client membentuk label PTS dan atlas dari ID lokal.

### GET /ranking/monthly/past

Query dan pagination sama. `scope` adalah PAST. Object season pada root tetap
menjelaskan bulan **berjalan**, agar client dapat memeriksa freshness. Setiap
item menyertakan season yang sudah selesai dan rank selalu 1.

```json
{
  "period": "CALENDAR_MONTH",
  "scope": "PAST",
  "snapshot_id": "test_past_202611_r5",
  "page": 1,
  "page_size": 50,
  "total": 1,
  "season": {
    "season_id": "2026-11",
    "starts_at_ms": 1793466000000,
    "ends_at_ms": 1796058000000
  },
  "items": [
    {
      "rank": 1,
      "club_id": 84,
      "club_name": "October Champion",
      "presentation_team_id": 108,
      "points": 10000,
      "season": {
        "season_id": "2026-10",
        "starts_at_ms": 1790787600000,
        "ends_at_ms": 1793466000000
      }
    }
  ]
}
```

Tidak ada runner-up di Past Season. Jangan memasukkan bulan berjalan,
menduplikasi bulan, atau membuat entry placeholder. items [] adalah respons sah.
Arsip tidak dibatasi jumlah season; client meminta 50 entry per halaman jaringan
dan menampilkan lima baris per layar. L/R mengganti Current/Past, analog scroll,
Y refresh dari halaman pertama. A pada entry tidak mengubah data.

### Snapshot pagination dan kegagalan

- snapshot_id berisi 1–64 karakter ASCII `A-Z a-z 0-9 _ -`, opaque bagi client.
  Ikat ke realm, scope, season, revision, page_size dan urutan hasil. Snapshot
  dapat dibagi antarsesi dalam realm yang sama agar ringan, TTL 10 menit.
- Permintaan memakai snapshot harus mengembalikan total dan urutan yang sama,
  termasuk saat kembali ke page 1 dari page 2. Kredit baru masuk snapshot baru.
  Y refresh atau berpindah Current/Past meminta snapshot baru.
- Snapshot kedaluwarsa: HTTP 409 `RANKING_SNAPSHOT_EXPIRED`, arahkan Refresh.
  Setelah bulan berganti: HTTP 409 `RANKING_SEASON_CHANGED` bagi snapshot lama.
  Jangan memberikan page sukses dengan snapshot_id atau season berbeda.
- Query/page tidak valid: 400 `INVALID_RANKING_PAGE`. Capability belum tersedia:
  503 `MONTHLY_RANKING_UNAVAILABLE`. Error tetap memakai envelope realm lengkap.
- Client mengganti halaman secara atomik setelah validasi payload. Payload
  salah tidak menimpa halaman terakhir. Saat reset, ranking bulan lama disembunyikan
  dan satu refresh otomatis dijadwalkan; respons stale tidak membuat loop request.

### GET /club/profile

Tambahkan object nullable, hanya untuk bulan berjalan:

```json
"monthly_ranking": { "season_id": "2026-11", "rank": 4, "points": 1500 }
```

Belum memiliki entry → null. `league_standing` existing tetap menunjuk tabel
W1/W2; jangan menggantinya dengan monthly_ranking. Field overall_rp lama boleh
dipertahankan untuk client lama, tetapi client v112 tidak memakainya sebagai PTS.

### GET /ranking/champions — riwayat liga W1/W2

Endpoint existing tetap array juara per liga/grup yang relevan bagi user.
Tambahkan `league_label: "W1" | "W2"` pada setiap entry, bersama cycle_id,
club_id, club_name, presentation_team_id dan settled_at yang sudah ada.
Riwayat ini tidak dihapus oleh pergantian bulan. Tidak digabung ke Past Season,
yang khusus juara ranking bulanan. Label UI: League Ranking History.

## Status LIVE pada tile HOME

Gunakan `GET /league/schedule` existing, bukan streaming atau endpoint per-frame.
Semua fixture yang dikembalikan harus berasal dari grup dan current cycle yang
sama dengan bootstrap/status. Per fixture:

```json
{
  "fixture_id": 55,
  "cycle_id": 15,
  "state": "LIVE",
  "broadcast_start_ms": 1793768400000,
  "broadcast_end_ms": 1793769060000,
  "duration_ms": 660000
}
```

Contoh disingkat: ID/nama kedua klub, presentation_team_id dan round_number
existing tetap wajib. state dihitung menggunakan clock realm saat GET: sebelum
kickoff SCHEDULED, start <= now < end LIVE, setelah end ENDED. Penghitungan skor
lebih awal tidak boleh membuat state ENDED sebelum jam tayang selesai.

Client hanya memasang badge jika fase Match Day, ada state LIVE dalam cache
cycle saat ini, dan waktu masih di interval siaran. Full time langsung
menghapus badge. Selama HOME Match Day, client refresh schedule tiap 30 detik
atau saat melewati kickoff/full time yang sudah diketahui, tanpa modal loading.
Tidak ada fetch per frame atau fetch recording hanya untuk badge. Data cache
lebih dari 90 detik tidak mengklaim LIVE saat jaringan tidak tersedia. Dengan
backend lama yang belum mengirim end/duration, digunakan durasi kontrak rekaman
existing 660.000 ms. Sebaiknya backend tetap mengirim kedua batas secara eksplisit.

## MySQL dan worker Go

Gunakan database PRODUCTION/TEST terpisah sesuai v106. Rekomendasi tabel:

| Tabel | Kunci dan kolom penting |
| --- | --- |
| ranking_seasons | season_id PK YYYY-MM, starts_at_ms, ends_at_ms, status OPEN/CLOSING/FINAL, finalized_at_ms |
| ranking_point_ledger | id PK, season_id FK, account_id, club_id, cycle_id, reason PARTICIPATION/PODIUM, delta, finish_position nullable, effective_at_ms; UNIQUE(cycle_id, account_id, reason) |
| ranking_monthly_totals | PK(season_id, account_id), club_id, points, participation_points, podium_points, wins_first, wins_second, wins_third, revision |
| ranking_monthly_champions | season_id PK/FK, account_id, club_id, club_name_snapshot, presentation_team_id_snapshot, points, finalized_at_ms |
| ranking_snapshots | id PK, realm/scope, season_id, revision, total, expires_at_ms; snapshot rows atau cache urutan compact |

Gunakan unsigned BIGINT untuk ID/timestamp/ledger sums, validasi DTO poin agar
masuk uint32 client. Index ledger `(season_id, account_id)` dan
`(effective_at_ms, id)`. Unique ledger berlaku lintas season sehingga pengulangan
worker tidak mengkredit event yang sama ke bulan baru. Tutup bulan mengarsipkan
total, tidak menghapus ledger atau wallet.

Join: lock membership/unique insert, tulis bonus wallet existing dan receipt,
tulis ledger +500 dan upsert total dalam transaksi MySQL yang sama. Worker
finalisasi liga: publish klasemen final, tulis ledger podium untuk manusia di
posisi 1–3, update totals dan outbox dalam satu transaksi. Duplicate key ledger
berarti sudah dikredit, jangan menambah total lagi. GET tidak menulis kredit.

Worker tutup bulan harus menguras semua event bertanggal sebelum cutoff
sebelum FINAL. Gunakan penguncian season dan urutan lock konsisten dengan writer:
transaksi join/hasil yang sudah melewati validasi waktu tidak boleh disusul
snapshot final yang melewatkan kreditnya. Replay pada bulan tertutup tidak boleh
mengubah champion. Setelah commit FINAL, buat/layani current season baru dan
invalidasi snapshot lama. TEST FINISH_WEEK/NEXT_MILESTONE menjalankan pipeline
yang sama dan memproses batas bulan yang terlewati secara berurutan.

Untuk VPS kecil, materialize totals dan top-one saat event terjadi. Jangan
memindai seluruh match tape pada setiap GET ranking. Snapshot urutan boleh
dibagi antaruser per realm, dipaginasi 50, dan dibersihkan sesudah TTL. Ini tidak
memerlukan service baru di luar container Go/MySQL/worker existing.

Migrasi dari Overall RP lama: backfill hanya dari immutable membership dan
official final-table records dengan timestamp asli serta unique ledger keys.
Jangan mengubah satu angka RP lama menjadi poin baru atau menebak posisi podium.
Data yang tidak terbukti dilaporkan sebagai gap migrasi, bukan diisi angka.
Uji backfill dua kali dan rebuild totals dari ledger harus menghasilkan hasil
identik. Aktifkan capability setelah endpoint, migrasi dan acceptance lulus.

## DEV OFFLINE dan verifikasi

DEV OFFLINE memakai susunan UI serta aturan poin yang sama, dihitung dari
fixture dan arsip save lokal. Tujuh klub mock ikut ranking lokal. Arsip lama
tidak menyimpan timestamp join; tanggal partisipasinya diinferensikan dari
kalender fixture dan tidak pernah diunggah sebagai poin online. Format save
tetap. Assist yang tidak direkam tape lokal tampil `--`, bukan angka karangan.
Mengubah mode offline tidak menyentuh wallet atau ranking TEST/PRODUCTION.

Acceptance backend sebelum capability diaktifkan:

1. Join sekali +500 PTS dan +1.500 NX Cash; retry/concurrent request sama tidak
   menggandakan keduanya. W1 dan W2 adalah membership berbeda.
2. Liga final: totals satu liga 2.500, 2.000, 1.500, 500; BOT tidak masuk global.
   Perhitungan awal rekaman tidak memberikan podium sebelum full time.
3. Batas bulan WIB, Desember–Januari, Februari kabisat, join sebelum cutoff dan
   podium setelah cutoff. Duplicate event lintas bulan tetap satu kredit.
4. Past hanya juara pertama setiap bulan; ties deterministik; season kosong,
   rename klub dan reset berkali-kali tidak menghapus/mengubah arsip juara.
5. Pagination lebih dari 50 dan lebih dari 256 peserta, navigasi balik, concurrent
   update totals, snapshot expiry, invalid scope/page dan pergantian bulan.
6. TEST dan PRODUCTION tidak berbagi ledger, snapshot, champion atau clock.
7. LIVE badge ada untuk siaran klub mana pun di grup berjalan, hilang di end,
   tidak muncul karena hasil precomputed atau cache cycle lalu. Clock TEST
   advance melewati kickoff/full time harus menghasilkan state yang benar.

Tes host client memeriksa parser atomik, capability gate, pagination 53 peserta,
tab, reset bulanan, leap year, tidak ada refresh storm, DTO Player Feed dan badge
LIVE. Preview menggunakan renderer C produksi dan contoh data lokal/sintetis;
ini tidak menggantikan uji jaringan deployment atau Switch fisik. Status
temuan live v110 tetap tercatat di [BACKEND-REVIEW.md](BACKEND-REVIEW.md).
