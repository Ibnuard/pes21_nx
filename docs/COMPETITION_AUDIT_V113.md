# Audit Cup League Master League dan Online League

**Tindak lanjut:** keempat temuan runtime di bawah sudah diperbaiki dalam
kandidat client v113. Hasil regresi dan retest backend tercatat di
[COMPETITION_FIXES_V113.md](COMPETITION_FIXES_V113.md). Uraian berikut adalah
rekaman audit sebelum perbaikan, bukan status kandidat terbaru.

29 Oktober 2026 WIB. Baseline adalah kode client v112 di working tree saat audit.
Empat bug client terkonfirmasi: Overtime League tidak mengikuti pengaturan,
refresh LIVE menahan input hub, cache klasemen melewati batas siklus, dan hasil
recheck kompatibilitas tidak mencabut izin online lama. Keempatnya masih terbuka.
Audit ini memperbaiki driver tes; kode runtime dan build v112 tetap sama.

## Temuan yang perlu diperbaiki

### League mengabaikan Overtime OFF saat knockout

**Prioritas P2.** General Setting menampilkan dan menyimpan Overtime OFF,
tetapi `competition_frontend_league_extra_time()` tetap mengembalikan true
untuk pertandingan knockout yang menentukan. Getter tersebut menguji fase dan
leg saja, tanpa membaca `cup_extra_time`. Native handoff memakai getter ini
untuk setter extra time, sehingga masalahnya memengaruhi aturan pertandingan.

Lokasi: [competition_frontend.c:623](../source/competition_frontend.c#L623),
[competition_frontend.c:2343](../source/competition_frontend.c#L2343),
[ue4_hooks.c:12616](../source/ue4_hooks.c#L12616).

Reproduksi host memakai frontend asli: buat League dua tim dengan sistem
knockout, matikan Overtime melalui General Setting, selesaikan pertandingan
tabel, lalu periksa aturan final. Hasilnya `OVERTIME label=OFF`,
`knockout extra_time=1`, `penalties=1`.

Perbaikan: getter extra time perlu menghormati setting pada deciding leg.
Pisahkan getter penalty dari getter extra time agar Overtime OFF tetap
memungkinkan adu penalti. Pertandingan tabel dan leg pertama tetap tanpa
extra time/penalty. Career knockout mempertahankan aturan kariernya sendiri.
Tambahkan tes matriks TABLE, leg pertama, leg kedua, final satu leg, dan
Overtime ON/OFF; verifikasi hasil getter yang dipakai native handoff.

### Refresh LIVE menahan input hub ketika jaringan lambat

**Prioritas P2.** Refresh schedule untuk badge LIVE mengirim request tanpa
modal loading. Namun semua request memasang `online.busy`, dan guard input
menolak seluruh tombol di halaman selain Watch selama busy. Tombol pindah tab
dan B ikut diabaikan. Saat request tertahan jaringan, batas HTTP 20 detik
menjadi batas potensi jeda kontrol tanpa petunjuk loading.

Lokasi: [manager_league_online_state.inc:609](../source/manager_league_online_state.inc#L609),
[manager_league_online.c:144](../source/manager_league_online.c#L144),
[manager_league_online_view.inc:78](../source/manager_league_online_view.inc#L78),
[manager_online_http.c:78](../source/manager_online_http.c#L78).

Reproduksi host mengirim `J_HUB_LIVE`, lalu menekan R dan B sebelum hasil
request dikonsumsi. Keduanya tidak mengubah tab/halaman, sementara busy true
dan modal_busy false. Ini membuktikan input tertahan; jeda 20 detik merupakan
konsekuensi timeout konfigurasi, bukan pengukuran jaringan Switch.

Perbaikan: bedakan request latar dari operasi pengguna. Navigasi lokal dan
Back perlu tetap bekerja; aksi yang memerlukan worker dapat diantrikan atau
mengambil prioritas dari refresh. Hasil refresh hanya boleh memperbarui cache
yang masih cocok account, realm dan cycle. Jangan melepaskan guard untuk
transaksi pembelian, grant, clock atau penyimpanan Game Plan secara umum.

### Klasemen lama tetap tampil sesudah perpindahan siklus

**Prioritas P2.** Bootstrap mengganti cycle/account dan mereset status prefetch,
tetapi tidak menghapus atau memberi tag siklus pada cache standings/news.
Hub memakai standing_count yang masih ada; Club Profile juga dapat mengambil
rank dari row selected lama. Jika pengambilan klasemen baru gagal, klasemen
liga sebelumnya tetap menjadi isi hub siklus baru setelah popup ditutup.

Lokasi: [manager_league_online_state.inc:130](../source/manager_league_online_state.inc#L130),
[manager_league_online_view.inc:398](../source/manager_league_online_view.inc#L398),
[manager_league_online_view.inc:294](../source/manager_league_online_view.inc#L294).

Reproduksi: isi cache standings siklus pertama, parse bootstrap W2 siklus
kedua dalam Preparation, lalu injeksikan transport failure untuk fetch tabel.
Setelah pesan koneksi ditutup, view W2 masih berisi row `PREVIOUS CYCLE`.
Kasus ini tidak memerlukan respons backend yang salah cycle.

Perbaikan: scope cache presentasi dengan `(environment, account_id, cycle_id)`.
Saat identitas scope berubah, batalkan cache tabel/feed/profile yang lama dan
tampilkan empty/loading state sampai respons baru valid. Refresh dalam scope
yang sama boleh mempertahankan data terakhir dengan status freshness. Simpan
recovery journal transaksi secara terpisah dan pertahankan key aslinya.

### Recheck kompatibilitas mempertahankan izin online lama

**Prioritas P2.** Pada respons kompatibilitas yang berbeda versi/hash, atau
maintenance aktif, handler menampilkan pesan tetapi tidak mengembalikan
`online.compatible` ke false. Setelah pernah lolos pemeriksaan, pengguna dapat
menutup pesan penolakan dan membuka route Login lagi dengan flag lama.

Lokasi: [manager_league_online_state.inc:466](../source/manager_league_online_state.inc#L466).

Reproduksi: login setelah compatibility sukses, kembali ke layar awal online,
lakukan recheck dengan required version berbeda, tutup pesan, lalu tekan A.
Hasilnya compatible tetap 1 dan halaman Login terbuka. Respons maintenance
menghasilkan perilaku yang sama. Gate backend yang benar tetap dapat menolak
request lanjutan; temuan ini adalah kegagalan gate client.

Perbaikan: cabut status kompatibel ketika recheck dimulai dan pada setiap
penolakan. Publikasikan compatible true hanya setelah seluruh pemeriksaan versi,
hash, runtime pair, katalog lokal dan maintenance berhasil. Tes perlu mencakup
urutan sukses lalu gagal, bukan hanya pemeriksaan pertama saat flag masih nol.

## Cakupan pemeriksaan

| Mode | Pemeriksaan dan hasil |
| --- | --- |
| Cup | 2.724 variasi dengan 2–32 tim, 1–8 pemilik manusia, bye, Home Away, final dua leg, bronze, dan tiga seed. Semua berakhir dengan champion; jumlah hasil sesuai peserta dan aturan bronze. Tes existing juga mencakup penalti, callback ganda, save gagal/retry dan fallback salinan rusak. Tidak ada bug core tambahan yang terkonfirmasi dari cakupan ini. |
| League | 1.792 variasi dengan 2–32 tim, pemilik manusia, Home Away, dua sistem kompetisi dan dua tie-break. Played/W/D/L/points/GF/GA konsisten dan kompetisi selesai. Overtime OFF pada frontend knockout adalah bug di atas. |
| Master League | 62 rollover musim dan 2.736 event untuk liga berukuran 2–32 klub. Invariant career diperiksa setiap event. Hasil dimainkan memberi kemenangan terkontrol bagi klub manager agar tes kalender tidak berhenti oleh pemecatan. Tes existing mencakup world/national events, transfer/kontrak, arsip, migrasi save dan adapter native. Tidak ada bug core tambahan yang terkonfirmasi dari cakupan ini. |
| Online League | Mock HTTP menjalankan controller/worker/parsers asli: paid pack, lost response, journal, realm, session refresh, Game Plan save, clock recovery, CDK, playback, pendaftaran dan ranking bulanan. Tiga bug frontend di atas terkonfirmasi melalui probe tambahan. |

Reproduksi menggunakan data sintetis dan temporary SaveData. Tidak ada operasi
pack, redeem, advance clock atau perubahan akun di server. Transisi native
Switch, adu penalti nyata, suspend saat jaringan aktif dan kehilangan daya saat
penulisan SD tetap memerlukan uji perangkat; keberhasilan host tidak menguji
ketahanan cache filesystem terhadap power loss.

## Perbaikan cakupan tes selama audit

Suite tambahan awal menemukan 2 kegagalan assertion dan 17 setup errors:

- Driver preview League belum menautkan `manager_league_client`, online HTTP,
  parser JSON dan loading popup yang kini dipakai `competition_frontend`.
- Fixture pack v99 masih bergantung pada konstanta epoch ranking 14 hari yang
  sudah dihapus, sehingga sebelas tes dalam kelas tersebut tidak dapat berjalan.
- Fixture kalender v98 masih mengharapkan match Selasa/Rabu dan Jumat/Sabtu,
  serta Demo Time langsung melompat ke kickoff. Aturan saat ini adalah Rabu dan
  Sabtu, dengan milestone Registration/Preparation sebelum kickoff.

Driver link diperbaiki dan fixture mengikuti kalender serta ranking bulanan
yang disepakati. Assertion transaksi tetap memeriksa debit/grant sekali,
pemulihan setelah restart dan kegagalan write. Assertion ranking kini memeriksa
reset tepat 1 November WIB, juara Oktober di Past Season, dan honours W1/W2
tetap tersedia. Subset yang diperbaiki lolos 25 tes dan 208 subtes.

Suite gabungan akhir mencakup 22 file tes dan lolos **140 tes serta 55.118
subtes**, termasuk geometri renderer. Sweep turnamen dan probe temuan di atas
dijalankan terpisah sehingga tidak dihitung sebagai tambahan tes pytest.

Probe dan bukti lokal berada di `local-debug/competition-audit-v113/`.
Kode gameplay belum diperbaiki pada tahap audit ini; empat temuan di atas
perlu regression test dan perbaikan client sebelum kandidat rilis berikutnya.
