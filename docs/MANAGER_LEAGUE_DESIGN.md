# FootballNX27 Manager League

Tanggal: 27 Oktober 2026

Revisi: dua liga per minggu, NX Cash, pack berbayar yang dapat dilanjutkan,
Touchline dan reset ranking dua minggu nyata
Status: prototipe lokal tersedia; simulator dan backend produksi belum dibuat.

Arahan terbaru beserta perilaku prototipe ada di
[review v99](MANAGER_REVIEW_V99.md). Kalender lama di bagian historis tidak
berlaku untuk musim baru: Senin/Kamis persiapan, Selasa–Rabu/Jumat–Sabtu
pertandingan, Minggu overview. Saldo belanja bernama NX Cash; League Point
dan reputasi terpisah. Saldo awal 5.000 NX Cash, bonus setiap ikut liga 1.500;
hadiah tambahan peringkat 1/2/3 adalah 5.000/4.000/3.000 NX Cash.

Dummy offline Switch untuk alur halaman, dashboard, siaran berdasarkan jam
kickoff dan seluruh replay musim contoh dijelaskan di
[MANAGER_LEAGUE_OFFLINE_DUMMY_V91.md](MANAGER_LEAGUE_OFFLINE_DUMMY_V91.md).
Dummy tersebut belum menerapkan backend, ekonomi atau simulator produksi.
State hub historis Pre-League hari 1–3, Match Day hari 4–6 dan Result hari 7,
terpisah dari tiga tab navigasi, diterapkan untuk dummy dalam
[MANAGER_LEAGUE_PHASES_V93.md](MANAGER_LEAGUE_PHASES_V93.md).
Satu hari demo dipercepat menjadi sembilan menit; ini bukan kalender server.

## Arah yang diminta

Manager League adalah kompetisi online asinkron. Pengguna mendaftar,
memberi nama tim, memilih klub apa saja sebagai identitas, lalu mendapat
skuad acak. Arahan terbaru mengubah starter dari "di bawah 60" menjadi
"OVR 60-an"; rancangan sekarang memakai rentang inklusif 60–69. Pemilihan
Barcelona atau klub lain tidak memberikan skuad asli atau kekuatan aslinya.

Aturan produk yang telah diminta atau dikonfirmasi pengguna:

- Satu minggu dunia nyata memuat dua musim liga.
- Persiapan Senin/Kamis; pertandingan Selasa–Rabu/Jumat–Sabtu; Minggu overview.
- Minimal tujuh tim terdaftar untuk memulai kompetisi.
- Setiap tim boleh bermain beberapa pertandingan per hari.
- Manajer baru menerima 5.000 NX Cash; setiap masuk musim liga mendapat 1.500.
- Juara 1/2/3 menerima tambahan 5.000/4.000/3.000 NX Cash; ranking terpisah.
- Database harus menyediakan daftar pemain beserta profilnya.
- Shop memakai pack pemain berdasarkan klub, misalnya Barcelona dan Madrid,
  dengan varian Lite, Medium dan Jumbo. API menentukan pack yang aktif.

Ukuran skuad, maksimum peserta per grup, harga pack dan jam kickoff
dan rumus ranking di bawah adalah default usulan, bukan angka yang telah
disetujui pengguna. Kontrak angkanya ada di `MANAGER_LEAGUE_RULES_V1.json`
dengan status `design_draft`; bukan konfigurasi runtime yang telah aktif.

Pertandingan peserta dijadwalkan setiap hari dan disimulasikan di backend.
Switch menampilkan pertandingan sebagai titik pemain dan bola di lapangan
2D, dengan pengalaman menonton dua babak lima menit dunia nyata.
Hasil sudah dihitung server sebelum visualisasi dimainkan. Backend dan VPS
belum dibuat atau dipilih; pembelian VPS mengikuti pembuktian prototipe.

## Loop pemain yang diusulkan

1. Daftar atau masuk, buat nama tim, lalu pilih identitas klub.
2. Terima satu kali skuad awal seimbang dan saldo awal 5.000 NX Cash,
   ditambah bonus 1.500 untuk setiap liga yang diikuti, termasuk liga pertama.
   Usulan skuad: 18 pemain, termasuk dua kiper.
3. Buka profil serta pasar pemain, lalu gunakan NX Cash untuk memperkuat tim.
4. Atur starting XI, formasi, pendekatan menyerang/bertahan, dan pergantian
   otomatis yang direncanakan. Lihat lawan serta deadline berikutnya.
5. Server mengunci pilihan pada deadline dan menjalankan pertandingan,
   termasuk untuk manajer yang sedang offline.
6. Tonton siaran simulasi 2D, atau lihat rekaman setelah jadwalnya berlalu.
7. Baca hasil dan klasemen. Sesudah seluruh fixture selesai, server membukukan
   hadiah serta ranking satu kali, lalu membuka persiapan minggu berikutnya.

## Kalender dan pendaftaran mingguan

Kalender mengacu pada Asia/Jakarta; deadline disimpan sebagai timestamp UTC.
Prototipe v99 menampilkan kalender tetap WIB agar siklus tidak berpindah hari
karena zona waktu perangkat. Backend produksi belum diimplementasikan.

| Hari | Tahap | Aturan |
| --- | --- | --- |
| Senin | Pre-League A / REGISTRATION | Daftar liga, belanja dan persiapan tim |
| Selasa–Rabu | Match Day A / COMPETITION | Beberapa round per hari, dua babak lima menit per laga |
| Kamis | Pre-League B / REGISTRATION | Daftar liga berikutnya dan persiapan tim |
| Jumat–Sabtu | Match Day B / COMPETITION | Beberapa round per hari, hasil setelah siaran terakhir |
| Minggu | OVERVIEW | Libur pertandingan dan review liga yang telah selesai |

Jendela pendaftaran adalah Senin 00:00 sampai Selasa 00:00 WIB, serta
Kamis 00:00 sampai Jumat 00:00 WIB, batas akhir
eksklusif. Server memakai waktu penerimaan dan transaksi pendaftaran, bukan
jam perangkat. Perintah yang dikirim sebelumnya tetapi baru diterima setelah
deadline tidak otomatis diterima. Cutoff dan transaksi peserta harus memakai
penguncian yang sama agar batas ketujuh tim tidak mengalami race.

Tujuh tim berarti tujuh klub dengan akun manajer berbeda yang lolos admission;
bukan tujuh sesi login, tujuh perangkat atau tujuh identitas klub berbeda.
Satu akun memiliki satu klub aktif dan satu entry per siklus liga, dua per minggu.
Pergantian lambang, nama atau reinstall tidak membuat entry maupun bonus baru.

Jika belum mencapai tujuh saat cutoff, siklus berstatus `NOT_STARTED_MINIMUM`.
Tidak ada pertandingan, hadiah, ranking atau pengisian bot diam-diam. Saldo
dan pemain yang sudah dimiliki tetap ada; pendaftaran minggu berikutnya
memerlukan persetujuan masuk antrean atau konfirmasi ulang yang terlihat.
Pengguna yang terlambat boleh membuat klub dan belanja untuk minggu berikutnya,
tetapi tidak disisipkan ke kompetisi yang sedang berjalan.

Usulan kapasitas: 7–16 tim per grup liga. Jika peserta lebih banyak, server
membagi otomatis ke grup seimbang. Untuk N >= 7, gunakan k=ceil(N/16), lalu
bagikan ukuran floor(N/k) atau ceil(N/k); contoh 17 menjadi 8+9, 21 menjadi
10+11. Semua peserta mendapat grup yang sah, tanpa sisa 1–6 tim dan tanpa
dipaksa memilih lawan. Penetapan grup dikunci, dicatat dan tidak dapat di-reroll.
Pemisahan berdasarkan pengalaman/kekuatan tim dapat ditambahkan setelah ada
populasi cukup; jangan mengklaim grup acak menjamin kekuatan lawan setara.

State siklus:

`REGISTRATION -> PARTICIPANTS_LOCKED -> COMPETITION -> SETTLING -> CLOSED`

Cabang minimum adalah `REGISTRATION -> NOT_STARTED_MINIMUM`. Status
`SUSPENDED` dipakai bila ada gangguan server yang belum terselesaikan;
deadline Minggu tidak membenarkan membuat skor atau juara dari laga yang hilang.

## Jadwal dan klasemen

MVP memakai single round robin: setiap pasangan bertemu tepat satu kali,
bukan kandang/tandang dua leg. Untuk N tim ada N(N-1)/2 pertandingan.
Jumlah round N-1 untuk N genap dan N untuk N ganjil. Tim ganjil mendapat
satu bye tanpa poin, gol, kemenangan, hadiah pertandingan atau lawan bot.
Setiap tim tetap memainkan N-1 laga. Satu tim tidak bermain dua kali dalam
round yang sama. Jumlah kandang/tandang per tim berbeda paling banyak satu.

| Tim per grup | Total laga | Round | Contoh pembagian round pada dua hari pertandingan |
| --- | --- | --- | --- |
| 7 | 21 | 7 | 4 / 3; setiap tim enam laga dan satu bye |
| 8 | 28 | 7 | 4 / 3; setiap tim tujuh laga |
| 16 | 120 | 15 | 8 / 7; setiap tim lima belas laga |

Contoh slot round: 12:00, 15:00, 18:00, 20:00, 22:00 WIB. Hari dengan
round lebih sedikit memakai slot awal. Batas taktik lima menit sebelum slot.
Setiap round memulai semua fixture independennya pada slot yang sama; round
berikutnya tidak boleh dibekukan sebelum seluruh hasil round sebelumnya sah.
Jika server terlambat, pertandingan ditandai tertunda dan waktu siaran baru
diumumkan. Jangan menampilkan siaran seolah berjalan sebelum rekamannya siap.

Poin klasemen 3/1/0 untuk menang/seri/kalah. Tie-break dikunci sebelum kickoff:
poin, selisih gol, gol memasukkan, lalu mini-table seluruh tim yang masih seri
(poin, selisih gol, gol memasukkan). Tidak ada rekursi mini-table. Jika tetap
sama, gunakan urutan undian server yang sudah dikomit sebelum kompetisi dan
diungkap saat penutupan; ID akun tua bukan keuntungan tiebreak.

Skuad, pembelian, katalog dan atribut dibekukan untuk dua hari kompetisi.
Taktik serta XI dari skuad yang dibekukan masih dapat diubah sebelum cutoff
tiap round. Jika tidak ada perubahan, gunakan taktik valid terakhir. Usulan
MVP mereset kondisi tiap laga serta belum menerapkan cedera atau suspensi
antar-laga; bye tidak memberi keuntungan pemulihan stamina. Red card dalam
laga tetap mengikuti aturan simulator yang dibekukan. Ini harus tertulis di UI.

Penarikan diri setelah peserta dikunci tidak menghapus hasil atau membuka
slot baru. Klub tetap disimulasikan dengan tim terakhir yang valid. Gangguan
login atau putus koneksi manajer tidak mengakibatkan WO. Sanksi administratif
memerlukan aturan konsisten, audit dan rekonsiliasi seluruh klasemen terdampak.

Saldo, skuad dan koleksi bertahan lintas minggu; jadwal serta klasemen grup
direset per siklus. Saldo awal 5.000 tidak diulang; setiap ikut liga menambah
1.500 NX Cash satu kali, lalu hadiah podium diberikan setelah seluruh laga.
Pengembangan
pemain, latihan dan transfer antarmanajer adalah perluasan setelah pembelian
dari pasar sistem stabil. Rancangan ini tidak menetapkan uang asli atau top-up.

## Skuad dan identitas

- Usulan katalog awal memakai pemain nyata yang terverifikasi dan memang
  berada pada rentang 60–69 dalam ruleset Manager League. Pemakaian nama
  pemain nyata versus pemain fiktif belum diminta secara eksplisit; katalog
  fiktif tetap pilihan terpisah yang memerlukan namespace identitas sendiri.
  Jangan menurunkan Messi menjadi starter 60 tanpa kebijakan versi yang jelas.
- Acak nama pemain sesuai posisi dan tanpa duplikasi dalam klub. Template
  starter mengunci distribusi OVR per posisi, kekuatan XI terbaik, stamina
  dan potensi pada batas setara; hanya rata-rata seluruh 18 pemain tidak cukup.
  Target roster 2 GK, 6 DEF, 6 MID, 4 FWD harus dapat membentuk XI legal.
  Jika katalog tidak cukup untuk memenuhi budget, tahan onboarding dengan
  alasan spesifik, jangan memberikan skuad yang lebih lemah atau donor.
- Starter dibuat satu kali oleh server dan disimpan dalam transaksi onboarding.
  Seed privat, batas reroll, versi katalog serta hash roster tercatat.
  Timeout atau reinstall mengembalikan roster yang sama, bukan undian baru.
- Pemilihan klub menentukan presentasi yang tersedia dari runtime lokal;
  nama tim milik manajer tetap tampil. Dua manajer boleh memilih identitas
  klub yang sama tanpa memiliki tim atau skuad database yang sama.
- Setiap klub dan kartu pemain yang dimiliki mempunyai ID Manager League
  tersendiri. Kartu milik dua klub dapat merujuk pemain katalog yang sama,
  tetapi progres dan kepemilikannya terpisah. Jangan menulis roster Manager
  League ke database native atau membuat donor PESDB.
- Pemain nyata memakai canonical BaseId dan fingerprint dengan mapping
  eksplisit. Native ID saja tidak membuktikan identitas. Satu klub maksimal
  memiliki satu instance aktif per pemain katalog, termasuk pemain starter.
- Presentasi klub/portrait yang memerlukan aset game tetap lokal dan ignored.
  Backend tidak memerlukan APK, OBB, CPK, PAK atau library game.

## Database pemain dan profil

Pisahkan katalog pemain dari kepemilikan, statistik kompetisi dan versi atribut.
OVR bukan satu-satunya input simulasi; profil terperinci harus benar-benar
digunakan dalam rumus, bukan sekadar hiasan UI.

| Entitas | Isi dan batas utamanya |
| --- | --- |
| accounts / clubs | Akun, klub tunggal, nama, identitas visual, status admission |
| player_catalog | catalog_id, jenis identitas, BaseId/fingerprint bila nyata, nama, posisi, kaki, usia acuan dan referensi profil |
| player_versions | Versi katalog/ruleset, attack, passing, technique, defense, pace, stamina, atribut GK, OVR turunan dan potensi |
| player_instances | instance_id, pemilik klub, catalog_id, versi atribut, asal starter/pembelian; unique klub+pemain aktif |
| roster_revisions / tactics | Revisi roster, XI legal, instruksi, hash; client harus mengirim expected revision |
| pack_offers / pack_pools / pack_purchases | Klub, tier, pool pemain beridentitas canonical, versi peluang, harga dan masa aktif; receipt pembukaan sekali per transaksi |
| wallets / ledger | Saldo integer nonnegatif, transaksi bertanda, reason, unique source key |
| seasons / league_groups / entries | Rentang waktu, ruleset hash, peserta dan grup terkunci; satu entry akun per liga, dua liga per minggu |
| rounds / fixtures / snapshots | Pasangan unik, slot round, cutoff, snapshot kedua tim dan seed privat |
| results / replay_chunks | Satu hasil fixture, kejadian bertimestamp, manifest, hash dan waktu rilis tiap potongan |
| season_awards / ranking_ledger | Posisi final, hadiah belanja dan RP terpisah, unique akun+siklus+jenis |

Profil yang terlihat: nama, posisi utama/tambahan, usia acuan, kaki dominan,
OVR, enam kelompok atribut dan GK bila relevan, kepemilikan, statistik musim
serta harga jika ditawarkan. Potensi/usia harus menyatakan tanggal acuan agar
tidak bergeser diam-diam. Portrait yang belum terbukti binding-nya memakai
placeholder yang jelas, tidak mengambil portrait pemain dengan native ID serupa.

Pembaruan katalog tidak mengganti atribut pertandingan berjalan. Satu musim
mengikat catalog_version, simulator_version, economy_version dan ruleset_hash.
Data pemain aktual hasil ekstraksi tetap lokal/ignored sesuai batas proyek;
yang dapat dipublikasikan adalah schema, importer dan logika buatan proyek.

## Ekonomi NX Cash

Bonus 5.000 adalah satu kali per akun yang menyelesaikan onboarding, termasuk
setelah retry request, perubahan nama/klub, reinstall dan pergantian musim.
Bonus partisipasi 1.500 diberikan satu kali untuk setiap liga yang diikuti,
termasuk liga pertama; saldo pertama setelah ikut liga menjadi 6.500 NX Cash.
Membuat banyak akun tetap risiko abuse; satu akun tidak membuktikan satu manusia.
Usulan beta memakai admission/invite, verifikasi akun dan audit pola transaksi.
Alamat IP atau konsol bersama bukan alasan otomatis menolak dua anggota keluarga.

Arahan terbaru mengganti rancangan beli pemain satuan dengan pack berdasarkan
klub. Contoh: Barcelona Pack dan Madrid Pack, masing-masing memiliki Lite,
Medium dan Jumbo. Harga poin, daftar pemain, bobot peluang serta jaminan OVR
belum ditetapkan. Rentang harga per pemain pada rancangan sebelumnya bukan
harga pack dan tidak menjadi batas OVR pack. Bonus awal 5.000 tetap satu kali.
Dummy v94 mengganti Scout Offer dengan tiga offer klub lokal untuk menguji UI,
pool, debit dan receipt. Harga 1.000/2.200/3.000 adalah harga contoh lokal,
bukan ekonomi produksi. Katalog dan transaksi server masih belum tersambung.

Jumlah hasil telah dikonfirmasi: Lite mendapat 2 pemain dari pool 5,
Medium 4 dari 6, dan Jumbo 5 dari 8, tanpa pengulangan dalam pembukaan yang sama. Arahan terbaru: pengguna memilih
sendiri subset tersebut setelah animasi pembukaan, lalu menekan Confirm yang
terpisah di bawah panel. Konfirmasi pembayaran sebelum animasi mendebit NX Cash
dan menyimpan pool berbayar. Konfirmasi pilihan kemudian memberikan pemain
tanpa debit kedua. Sesudah pembayaran tidak ada Back; keluar aplikasi tidak
menghilangkan pool atau pilihan, dan login/shop melanjutkan pilihan yang sama.
Pool offer lokal tetap terikat katalog dan starter awal; membuka receipt lagi
tidak mengundi ulang atau mendebit poin lagi. Kapasitas skuad terdaftar 25,
dengan koleksi terpisah dan aksi mengganti reserve dari koleksi. Placeholder
klub native dipakai sebelum pemilihan; klub nyata tidak memberi skuad aslinya.

Daftar pack berasal dari API, sehingga aktivasi, penghentian dan rotasi pack
tidak memerlukan build NRO baru. Kontrak usulan katalog menyertakan waktu
server, versi katalog, ID offer, ID klub, tier, versi pool, masa aktif,
harga poin, aturan jumlah hasil, peluang yang ditampilkan, batas pembelian
dan status eligibility akun. UI memperlihatkan aturan jumlah hasil, harga
dan masa aktif sebelum konfirmasi, tanpa preview identitas pemain sebelum
pembukaan. Pool versi yang dibeli disimpan untuk pemilihan sesudah pembayaran.
Cache lama boleh ditampilkan sebagai informasi; API produksi tetap harus
memvalidasi ulang sebelum menerima pembelian.

Kontrak server mengikuti dua tahap idempoten: pembayaran dan penyimpanan pool
lebih dahulu, lalu validasi subset serta pemberian instance pemain. Client
memutar animasi pool berbayar tersebut. Putus koneksi, retry atau menonton
animasi lagi harus mengembalikan pool yang sama tanpa debit atau undian ulang. Pembelian
mengikat versi offer/pool/peluang yang dikonfirmasi; perubahan harga, masa
aktif berakhir, atau penutupan Match Day memerlukan penolakan sebelum debit.
Client mengirim ID pemain terpilih; server memeriksa keanggotaan pool,
keunikan, jumlah pilihan, versi offer, saldo dan eligibility sebelum grant.

Usulan: tidak ada pemain berulang dalam satu pembukaan. Penanganan pemain
yang sudah dimiliki, batas koleksi dan peluang/garansi tiap tier masih
memerlukan aturan produk. Kapasitas skuad aktif usulan 25 tidak cukup untuk
18 starter ditambah lima hasil Jumbo dan hasil pack lain. Solusi usulan memisahkan
koleksi pemain dari skuad terdaftar, sehingga seluruh hasil tersimpan lalu
manajer memilih skuad yang sah saat Pre-League. Jangan membuang hasil,
memotong jumlah hadiah atau mendebit pack yang tak dapat ditampung.

Pasar terbuka saat REGISTRATION dan setelah hasil final, serta ditutup selama
dua hari pertandingan pada setiap liga. Klub yang belum masuk liga dapat belanja untuk liga
berikutnya. Snapshot roster kompetisi tetap tak berubah.

Pembayaran adalah transaksi tunggal: verifikasi pemilik, jendela, versi pack,
pool, kapasitas dan kebijakan duplikasi; debit saldo bersyarat; simpan pool
berbayar, ledger dan receipt. Kegagalan sebelum commit membatalkan debit.
Grant merupakan transaksi berikutnya yang menutup receipt berbayar sekali;
kegagalan grant mempertahankan pool dan hak pilih. Dua request paralel tidak boleh
menghasilkan saldo negatif. Idempotency key terikat akun+operasi+hash payload;
penggunaan ulang dengan payload berbeda ditolak, bukan membeli dua kali.
Harga, saldo, OVR dan pemilik tidak diterima dari nilai yang dipilih klien.

## Hadiah dan ranking

Tiga nilai berbeda harus mempunyai nama serta tampilan berbeda:

- League Point: 3/1/0, hanya untuk tabel grup pada liga tersebut.
- NX Cash: saldo yang dipakai membeli pemain, persisten lintas liga.
- Ranking Points (RP): prestasi manajer, tidak dapat dibelanjakan.

Hadiah yang dikonfirmasi per liga: juara 5.000 NX Cash, runner-up 4.000,
peringkat tiga 3.000. Hadiah ini tambahan dari bonus partisipasi 1.500;
peserta lain tidak mendapat hadiah akhir tambahan. Tidak ada bonus per gol, replay yang ditonton atau
pengiriman hasil dari klien. Hadiah hanya untuk grup valid dengan semua fixture
resmi selesai; grup gagal mulai tidak mendapat hadiah atau RP.

Overall Rank direset setiap 14 hari nyata, Senin 00:00 WIB, dengan anchor
26 Oktober 2026. UI menampilkan tanggal reset berikutnya. Prototipe tujuh tim
mempertahankan RP hasil liga 700/600/500/400/300/200/100; kontribusi berasal
dari hasil liga lengkap dalam jendela tersebut, tanpa prestise awal buatan.
Rumus produksi lintas ukuran grup belum diputuskan. Riwayat League Champions
tetap tersedia sesudah reset, termasuk nama, lambang dan hasil musim aslinya.

Saldo, pemain dan gelar tidak direset. Statistik klasemen berganti setiap liga;
Overall RP hanya mencakup jendela 14 hari saat ini. Pemisahan divisi
rookie/berpengalaman atau rating kekuatan lawan adalah perluasan, bukan klaim
bahwa rumus RP ini sudah menyelesaikan seluruh persoalan fairness.

Settlement menghitung tabel dari hasil resmi, memvalidasi seluruh jadwal,
lalu membukukan award/ledger satu kali per akun dan siklus. Penutupan dan
ranking baru tampil setelah cohort settlement lengkap, bukan setelah subset
akun berhasil. Retry worker atau membuka layar hadiah tidak memberi poin lagi.
Koreksi administratif membuat transaksi kompensasi tercatat, tidak menghapus
history ledger atau menghitung ulang saldo dengan perubahan tersembunyi.

## Satu simulasi untuk hasil dan tayangan

Gunakan simulator sepak bola 2D buatan proyek yang berjalan tanpa renderer.
Jangan mengasumsikan library pertandingan PES Mobile dapat dijalankan di VPS.
Simulator lokal Cup/League yang ada belum membuktikan lintasan titik, pengaruh
taktik, atau kelayakan backend Manager League.

Input tiap round dibekukan pada cutoff-nya sebagai snapshot kedua skuad,
taktik, kondisi, versi aturan dan seed server. Seluruh hasil tiga hari tidak
dihitung saat pendaftaran ditutup, sebab itu akan mengabaikan perubahan taktik
untuk round berikutnya. Simulator menghasilkan urutan kejadian serta
keadaan pemain/bola. Gol, statistik dan hasil akhir diturunkan dari urutan
yang sama. Titik tidak bergerak acak mengikuti skor yang dibuat terpisah.
RNG starter, pengelompokan, jadwal, undian tiebreak dan simulasi mempunyai
domain seed terpisah. RNG simulator memakai implementasi integer yang
berversi serta aturan pembulatan eksplisit agar hasil tidak bergantung pada
versi pustaka atau arsitektur host. Reproduksi seed harus dibuktikan melalui
hash event/hasil, bukan diasumsikan dari label "deterministik".

Seed dan versi aturan disimpan untuk reproduksi internal, bukan untuk klien
memilih atau menjalankan ulang hasil pertandingan.

Durasi 180 detik adalah target presentasi, bukan kewajiban setiap job server
memakan tiga menit CPU. Waktu komputasi, ukuran rekaman, dan kapasitas VPS
harus diukur. Pilihan awal adalah ringkasan dengan fase serangan penting dan
transisi waktu pertandingan; bukan janji menampilkan setiap detik 90 menit.
Semua kejadian yang memengaruhi hasil tetap harus terwakili secara konsisten.

State machine usulan:

`SCHEDULED -> LOCKED -> COMPUTING -> SEALED -> PUBLISHED`

Kegagalan komputasi dapat dilanjutkan dari snapshot LOCKED yang sama. Setelah
SEALED, hasil dan rekamannya tidak ditimpa oleh perubahan taktik, reconnect,
refresh atau pergantian versi simulator. Perbaikan hasil setelah publikasi
memerlukan prosedur administratif tercatat, bukan simulasi ulang diam-diam.

## Siaran, replay, dan taktik

Untuk jadwal bersama, server menetapkan waktu mulai siaran dan membuka
potongan rekaman sesuai waktu server. Klien yang terlambat dapat mengikuti
posisi siaran saat itu; replay penuh tersedia setelah siaran berakhir.
Pengguna yang offline tetap mendapat hasil dan dapat menonton nanti.

Jika seluruh rekaman dikirim sebelum siaran selesai, skor akhir dapat dibaca
lebih awal oleh klien yang dimodifikasi. Untuk menahan spoiler, jangan kirim
hasil akhir, klasemen yang membocorkan hasil, seed privat atau potongan masa
depan sebelum waktu publikasinya. Antrean siaran tetap hanya mendistribusikan
rekaman; tidak memerlukan sinkronisasi input pertandingan antar-Switch.

Tampilkan label seperti "SIARAN SIMULASI" atau "REPLAY" sesuai konteks.
Semua penonton pertandingan menerima kejadian yang sama. Visual titik dapat
diinterpolasi lokal, sedangkan gol dan statistik mengikuti timestamp rekaman.

MVP memakai taktik dan pergantian otomatis yang dikunci sebelum pertandingan.
Mengganti taktik saat menonton rekaman tidak dapat mengubah hasil yang telah
SEALED. Coaching interaktif saat pertandingan adalah cakupan berbeda yang
memerlukan komputasi bertahap dan aturan waktu bersama.

## Pembagian komponen yang diusulkan

| Komponen | Tanggung jawab |
| --- | --- |
| Switch | Akun, skuad, formasi, jadwal, lapangan titik, statistik dan replay |
| API HTTPS | Otentikasi, hak akses tim, validasi perintah dan pembacaan data |
| Scheduler/worker | Mengunci deadline, membuat job dan menghitung simulasi |
| Database | Akun, tim, pemain, musim, fixture, snapshot, hasil dan transaksi |
| Rekaman pertandingan | Metadata versi, potongan kejadian/posisi dan hash |

Awal yang disarankan adalah satu deployment kecil dengan database dan satu
worker, bukan banyak layanan terpisah. Bahasa backend dan penyedia VPS masih
terbuka. HTTP cukup untuk perintah dan pengambilan potongan siaran; koneksi
WebSocket bukan syarat simulasi asinkron. Gunakan waktu server UTC, tampilkan
jadwal pada zona waktu pengguna, serta verifikasi sertifikat TLS pada klien.
Kredensial akun dan token otorisasi tidak masuk source publik atau log.

Server memiliki roster, atribut, uang, aturan dan hasil. Klien mengirim
pilihan yang diminta, bukan OVR baru, saldo atau skor. Pendaftaran dan perubahan
skuad harus idempotent. Job dapat dicoba lagi, tetapi satu fixture hanya boleh
memiliki satu hasil resmi dan satu pembukuan klasemen/hadiah.

Usulan implementasi database: unique fixture/result key, transaksi dan locking
untuk publikasi hasil, dengan reward ledger berkunci unik. Rekaman diselesaikan
dan diperiksa hash-nya sebelum hasil dipublikasikan; file rekaman dan database
tidak dianggap otomatis atomik. Saldo dan klasemen tidak bergantung pada apakah
klien menonton replay atau mengirim konfirmasi selesai.

Worker boleh mengambil ulang job setelah lease kedaluwarsa, tetapi setiap
commit memeriksa fencing token/versi job. Worker lama yang terlambat tidak
boleh menimpa hasil worker baru. Scheduler tidak diberi asumsi exactly-once;
job diproses at-least-once dengan efek transaksi idempotent. Deadlock atau
serialization failure mengulang seluruh transaksi dengan batas retry, bukan
mengulang debit/grant di luar transaksi. Rekonsiliasi membandingkan saldo
dengan ledger, tabel dengan hasil resmi, serta manifest dengan hash rekaman.

## Urutan pembuktian

1. Katalog/profil terverifikasi, onboarding starter 60–69, wallet 5.000 satu
   kali, pasar sistem serta aturan ekonomi dalam prototipe lokal. Jangan
   mengimpor roster native atau menyebarkan database sumber ke Git.
2. Simulator lokal dua skuad dan visualisasi titik; tunjukkan hubungan atribut,
   formasi serta taktik dengan alur pertandingan. Ukur durasi dan ukuran data.
3. Rekaman 600 detik yang menghasilkan skor/statistik identik pada dua penonton,
   termasuk pause, seek dan reconnect.
4. API serta worker lokal untuk satu grup 7–16, dua siklus 1+2 hari per minggu, jadwal lengkap,
   settlement hadiah/ranking dan peserta offline. Uji dua pembelian paralel,
   request onboarding berulang, worker lama, lease expiry, hasil hilang dan
   hadiah dua kali. Durasi kalender dapat dipercepat hanya pada lingkungan tes.
5. Integrasi klien Switch, cache, jaringan terputus, resume dan pengukuran UI.
6. Load test puncak kickoff, backup/restore dan pemulihan worker, lalu pilih VPS
   berdasarkan hasil ukur. Setelah itu baru perluas latihan atau P2P transfer.

## Kriteria penerimaan dan kegagalan yang wajib ditolak

| Skenario | Hasil yang diwajibkan |
| --- | --- |
| Cutoff hanya enam tim | Tidak mulai; tidak ada hadiah/RP; aset akun tetap |
| Tujuh tim | 21 laga, tujuh round, enam laga+bye satu kali per tim |
| 16 tim | 120 laga, 15 round, dibagi delapan dan tujuh round selama dua hari |
| Lebih dari 16 peserta | Grup seimbang 7–16; satu entry per akun dan siklus |
| Klub Barcelona versus klub Barcelona | Instance klub/roster terpisah, tidak berbagi kepemilikan |
| Onboarding timeout/retry/reinstall | Roster dan bonus 5.000 tetap satu kali |
| Starter di luar 60–69 atau XI tidak legal | Onboarding ditolak sebelum grant dipublikasikan |
| Dua pembelian paralel melebihi saldo | Hanya pembelian yang sah commit; saldo tidak negatif |
| Idempotency key sama, payload berbeda | Konflik eksplisit; tidak debit/menambah pemain |
| Request milik klub lain | Ditolak oleh otorisasi server |
| Roster/taktik berubah setelah cutoff | Ditolak atau diarahkan ke revisi round berikutnya |
| Simulasi dijalankan ulang dari snapshot sama | Hash hasil dan event sama; satu hasil resmi |
| Lease worker lama selesai belakangan | Commit ditolak oleh fencing token |
| Rekaman rusak atau goal events tidak cocok skor | Tidak dipublikasikan dan tidak diberi hadiah |
| Server padam menjelang Minggu | SUSPENDED/pemulihan terlihat; tidak membuat juara palsu |
| Membuka hadiah atau menjalankan settlement berulang | Receipt sama; satu ledger grant dan satu kontribusi RP |
| Ada fixture belum final | Grup belum CLOSED dan hadiah belum tersedia |
| Dua penonton/reconnect | Gol, skor dan statistik identik; tidak mengubah hasil |
| Klien mencoba membaca masa depan siaran | Chunk, seed dan tabel pembocor belum dirilis |

Tidak ada backend atau simulator yang di-hardening melalui dokumen ini saja.
Angka ekonomi memerlukan simulasi beberapa musim dan uji pilihan belanja;
kekuatan starter memerlukan katalog nyata dan uji pengaruh atribut. Kapasitas
server, performa Switch, keamanan transaksi dan kualitas tayangan belum diuji.

## Referensi arsitektur

- [Server-authoritative multiplayer](https://heroiclabs.com/docs/nakama/concepts/multiplayer/authoritative/):
  server memvalidasi aturan dan memiliki state resmi. Referensi pola; belum
  memutuskan penggunaan Nakama.
- [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
  dan [explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html):
  alat untuk menjaga keunikan dan akses bersama. Jaminan publikasi satu kali
  tetap bergantung pada desain transaksi, job dan ledger aplikasi.
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html):
  penanganan transaksi paralel dan pengulangan seluruh transaksi yang gagal.
- [OWASP business logic security](https://cheatsheetseries.owasp.org/cheatsheets/Business_Logic_Security_Cheat_Sheet.html):
  otoritas nilai di server, workflow eksplisit, race, idempotency dan uji abuse.
