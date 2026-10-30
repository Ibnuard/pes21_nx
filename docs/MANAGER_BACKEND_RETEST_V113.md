# Retest deployment backend v113

29 Oktober 2026 WIB. Menggunakan endpoint HTTPS deployed, akun operator TEST
yang sudah diizinkan, dan parser/controller C produksi dari client v113.
Referensi kontrak tetap [hub v111](MANAGER_HUB_V111.md) dan
[hub v112](MANAGER_HUB_V112.md). Source client tidak diubah atau dibangun ulang;
238 hash source/build sama dengan kandidat NRO v113 yang telah dikirim.

## Perbaikan yang sudah terverifikasi

| Area | Hasil |
| --- | --- |
| Ranking bulanan | Current Season sekarang selalu mengirim participation_points, termasuk 0. Current/Past diterima parser. points = participation + podium. |
| Bonus join | Join cycle 16 menambah wallet 19.500 → 21.000 dan monthly points 4.000 → 4.500, participation 0 → 500. Replay key yang sama tidak menambah kredit kedua. |
| Pendaftaran/BOT | Satu manusia di Registration; saat Preparation menjadi empat peserta dengan tiga BOT dan enam fixture round-robin. |
| Fase | Cycle 16 baru melewati REGISTRATION, PREPARATION, MATCH_DAY dan LEAGUE_END; bootstrap/status sesuai. Bootstrap league:null sebelum join diterima sebagai fallback ke /league/status, bukan error. |
| Player Feed lama | Cycle 15 kini punya cycle_id, watermark valid dan list kosong tanpa entry goals/assists nol buatan; diterima parser. Cycle baru masih gagal, lihat temuan 2. |
| Playback | Dua full tape LIVE dari fixture 59 dan 61 diterima: 22 chunk per GET. Score/touchline diperiksa pada 661 posisi per tape, total 1.322 posisi; event masa depan tidak ditampilkan pada posisi sebelum waktunya. |
| Recovery/gate | GET clock operation dan POST replay sama revision/waktu receipt. Stale revision 409; token TEST dengan assertion PRODUCTION pada GET ditolak 403. Invalid monthly page 400; permintaan page 1 dengan snapshot_id sama stabil. |

Clock diuji revision 16 → 27, sebelas advance unik disertai lookup/replay.
Ada satu join dengan replay key/body sama. Tidak ada pack purchase, grant, CDK,
akun baru atau mutasi dengan header PRODUCTION. Pengujian ini tidak memeriksa
database produksi secara langsung. Respons/token/tape mentah hanya disimpan
lokal di direktori ignored, bukan dalam handoff publik.

## Empat temuan yang masih perlu diperbaiki

### 1. P2 — replay join mengubah metadata TEST menjadi PRODUCTION

POST `/league/join`, token operator TEST, header X-FNX-Environment: TEST, body
{} dan satu Idempotency-Key. Respons pertama 201 memiliki meta.environment TEST,
cycle 16, entry 41, credit ledger 22 dan wallet 21.000. Ulangi request yang sama:
status tetap 201 dan receipt ledger/wallet sama, tetapi meta.environment berubah
menjadi PRODUCTION; server_now_ms ikut memakai waktu nyata produksi.

Ini dibuktikan lewat `consume()` client: guard realm menampilkan ENVIRONMENT
MISMATCH sebelum handler join. Kredit ganda tidak terjadi pada tes ini. Metadata
yang salah tidak membuktikan bahwa transaksi masuk database produksi.

Perbaikan: cache receipt/idempotency data dan status HTTP tanpa membekukan
envelope request. Bangun meta dari authenticated realm serta domain clock yang
benar pada setiap replay. Jangan memakai helper response default PRODUCTION
untuk cabang replay. Audit jalur generic yang sama pada pay/grant/promotion dan
mutasi lain; hanya join yang ditulis/replay dalam retest ini. Acceptance: request
pertama, exact replay dan recovery memakai realm TEST, clock TEST, satu ledger,
satu membership, dan dapat dikonsumsi client tanpa menonaktifkan guard.

### 2. P2 — clock SUCCEEDED belum menghasilkan publikasi kompetisi lengkap

Reproduksi memakai **liga baru cycle 16**, bukan hanya data lama sebelum deploy:
join Thursday, advance Preparation (empat tim/3 BOT), lanjut Match Day, tiga
round serta full time terakhir. Pada revision 27, bootstrap dan status sudah
LEAGUE_END; schedule berisi enam fixture 61–66 ENDED dengan skor 0–0. Namun
GET `/league/standings` mencatat played=0 dan points=0 pada keempat klub.
Single round-robin empat tim seharusnya menghasilkan played=3 per klub; untuk
enam skor seri 0–0, setiap klub memiliki drawn=3 dan points=3.

GET Player Feed masih mengirim:

```json
{"cycle_id":16,"published_through_ms":0,"rising_stars":[],"top_scorers":[]}
```

List kosong sah bila tidak ada gol/assist, tetapi watermark wajib valid dan
tidak boleh melebihi server_now_ms. Parser menolak snapshot ini pada Match Day
dan League End. `/news` juga belum mempunyai hasil fixture cycle baru, sedangkan
monthly points tetap 4.500 sesudah siaran terakhir. Belum ada bukti publikasi
tabel akhir/poin podium cycle baru. Wallet tidak diharapkan menerima podium
sebelum settlement Minggu; tidak ada temuan tentang cash podium dini.

Recheck beberapa request kemudian tetap played=0/watermark=0. Cycle 15 lama
juga masih played=1 ketika enam fixture sudah ENDED; sebelum simulasinya lengkap
bahkan ada dua ENDED dengan score null. Perbaikannya harus mencakup proses baru
dan rekonsiliasi fixture yang sudah telanjur selesai.

Acceptance: pipeline advance menyimulasikan rekaman yang diperlukan, lalu
memublikasikan setiap hasil yang telah melewati FT tepat sekali, memperbarui
W/D/L/GF/GA/points, watermark, news dan final-table monthly podium. Jika kerja
masih asynchronous, status operation tetap RUNNING sampai pipeline selesai.
Watermark feed berasal dari checkpoint publikasi, termasuk pertandingan tanpa
gol; jangan mengambil MAX dari row kontribusi lalu mengubah NULL menjadi 0.
Replay/worker restart tidak boleh menambah played/PTS/news dua kali. Tambahkan
assertion nilai tabel dan ledger, bukan hanya label ENDED/HTTP 200.

### 3. P2 — schedule mengembalikan grup liga sebelumnya

Pada Registration cycle 16, `/league/status` benar mengirim W2/user_joined=false.
Bootstrap league:null masih sah sebelum ikut. Tetapi `/league/schedule`
mengembalikan fixture 55–60 cycle 15/grup 10; sesudah join cycle 16 pun sama
hingga grup baru terbentuk pada Preparation. Standings juga masih berisi grup
lama saat Registration. Guard scope client menolak schedule tersebut, sehingga
prefetch hub menampilkan SERVER DATA UPDATE.

Scope query ke current cycle/window serta membership yang benar, bukan latest
historical group milik klub. Belum ada grup current cycle → schedule []; jangan
memakai fallback grup lama. History tetap melalui route/parameter history yang
eksplisit. Acceptance: W1 selesai → W2 Registration sebelum join → sesudah join
→ Preparation; setiap fixture mengikuti current cycle, atau list kosong sebelum
grup terbentuk. Riwayat W1 tetap tersedia pada history tanpa mencampur cache W2.

### 4. P2 — advance pertama memundurkan clock TEST existing

Sebelum advance pertama, revision 16 memberi server_now_ms=1793779303237 dan
phase LEAGUE_END. NEXT_MILESTONE dengan expected_revision 16 berhasil ke revision
17, tetapi test_now_ms=1793771760000, sekitar 126 menit lebih awal. State kembali
MATCH_DAY dan fixture yang sudah tampil ENDED kembali SCHEDULED/LIVE pada clock
yang mundur. Lookup dan replay konsisten dengan receipt yang mundur itu.

Advance selanjutnya pada state yang baru tidak menunjukkan rollback lagi dalam
tes ini. Jadi pastikan migrasi/rekonsiliasi TEST clock existing juga tertangani,
bukan hanya akun/clock baru. Kemungkinan perhitungan masih memakai anchor lama
yang tertinggal dari domain now; penyebab source belum diverifikasi karena
repository backend tidak berada dalam workspace ini.

Acceptance: ambil now realm saat transaksi advance, pilih milestone sesudahnya,
CAS revision dan simpan checkpoint baru tanpa mundur. Uji idle sebelum advance,
reload/deploy, perubahan mode running/frozen dan retry. Jangan menghapus atau
mengulang kredit/publication untuk mengatasi rollback.

## Batas hasil dan tindak lanjut

Harness C menjalankan 123 parse payload yang diterima, 10 yang ditolak, satu
HTTP gate, ditambah satu tes negatif yang membuktikan join replay ditolak guard
realm. Penolakan adalah schedule salah cycle dan feed watermark 0 di atas.
Fixture negatif tidak dilonggarkan agar server dianggap lulus.

Isi `/news` lama sekarang ada, tetapi masih berbentuk legacy tanpa
occurred_at_ms/league_label, sehingga konteks tanggal/W1/W2 pada feed belum
terisi sesuai v111. Lengkapi metadata structured feed saat memperbaiki outbox
publikasi. Kontribusi pemain dengan gol/assist positif belum dapat diverifikasi
karena seluruh skor liga TEST ini 0–0 dan pipeline publikasi belum lengkap.

Belum ada pengujian Switch fisik atau klaim seluruh backend siap produksi.
Tidak diperlukan NRO baru untuk menutup masalah server di atas; retest parser
yang sama setelah backend diperbaiki, kemudian acceptance perangkat.
