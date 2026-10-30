# Perbaikan audit kompetisi v113

29 Oktober 2026 WIB. Menindaklanjuti empat temuan pada
[audit kompetisi](COMPETITION_AUDIT_V113.md). Tidak ada perubahan format save,
aturan turnamen inti, ledger backend atau saldo wallet dari perbaikan ini.

## Perilaku yang diperbaiki

- **League:** getter native extra time mengikuti Overtime ON/OFF pada fixture
  knockout penentu. Penalti memakai pemeriksaan deciding fixture tersendiri;
  Overtime OFF tetap boleh berakhir dengan adu penalti. Table dan leg pertama
  tanpa keduanya. Aturan knockout Master League tetap mengikuti karier.
- **Hub online:** GET badge LIVE tidak menahan analog, pindah tab atau Back.
  Satu aksi API pengguna dapat menunggu worker dengan popup loading; request,
  UUID dan journal disiapkan sekali. Hasil refresh latar hanya memperbarui cache
  untuk generation, environment, account dan cycle yang sama. Error latar tidak
  mengarahkan halaman, membuka popup atau memulai session refresh. Guard untuk
  pembayaran, grant, save Game Plan dan Demo Time tetap aktif.
- **Cache:** perubahan akun, realm atau cycle membatalkan tampilan standings,
  schedule, feed dan rank profil sebelumnya. Bootstrap dalam scope yang sama
  boleh mempertahankan snapshot valid. Draft Game Plan dan recovery journal
  transaksi tidak dihapus oleh invalidasi cache presentasi. Pengambilan schedule
  memublikasikan array setelah validasi utuh; respons terpotong tidak menimpa
  cache valid.
- **Compatibility:** status kompatibel dicabut saat recheck dimulai dan saat
  hasilnya ditolak, rusak, gagal jaringan atau maintenance. Versi, hash, pair,
  schema dan boolean maintenance wajib valid sebelum Login diizinkan lagi.

Retest backend juga menemukan state PREPARATION yang tertinggal saat Match Day
sudah berlangsung. Jika jadwal resmi sudah melewati kickoff dan masih dalam
rentang cycle yang sama, hub memakai batas siaran tersebut untuk akses Match
Centre serta countdown Match Day/League End. Fallback ini tidak mengarang cycle
baru dan tidak mengaktifkan pendaftaran. Backend tetap perlu menyelaraskan
label state; temuan dan contoh koreksinya ada di [BACKEND-REVIEW.md](BACKEND-REVIEW.md).

## Verifikasi

Regresi host menggunakan frontend/controller/parser produksi, mock HTTP, dan
SaveData sintetis dalam temporary directory. Matriks League mencakup Table,
knockout dua/empat tim, satu/dua leg, first/deciding leg dan Overtime ON/OFF.
Tes online mencakup navigasi saat badge pending, antrean pembelian dengan
journal yang sama, penolakan response lintas scope, bootstrap cycle/account
baru setelah fetch gagal, draft tetap ada, serta compatibility sukses lalu
version/hash/pair/maintenance/malformed/transport/HTTP gagal.

Hasil akhir gabungan: **146 tes unik dan 55.118 subtes lolos**. Suite lintas
mode awal meloloskan 127 tes, sementara 18 tes renderer Master League terkena
timeout setup 60 detik saat WSL memulai build. Pengulangan subset tersebut
sendiri meloloskan 18 tes dan 54.774 subtes. Subset online final meloloskan
50 tes, termasuk regresi label fase yang ditambahkan setelah collection suite
awal; total unik menjadi 146. Matriks Overtime baru juga lolos. Tidak ada
assertion yang dilonggarkan atau timeout tes yang dinaikkan.

Retest HTTPS nyata hanya memakai TEST untuk autentikasi, read dan satu
NEXT_MILESTONE dengan lookup/replay key yang sama. Full tape ENDED diterima
parser dan diperiksa pada 661 posisi playback; full tape LIVE tersedia lewat
satu GET serta diterima parser tanpa menampilkan event masa depan pada kickoff.
Current Season dan Player Feed masih ditolak karena payload backend
belum sesuai kontrak, sementara Past Season diterima. Tidak ada test pembelian,
redeem CDK atau mutasi PRODUCTION pada retest ini.

Kandidat NRO memakai runtime pair `e861c583ec78e9ae` dan dummy OBB 53.248 byte,
sama dengan v112. Update hanya NRO; SaveData, aset lokal dan journal transaksi
tetap diperlukan. Host test/build tidak menggantikan acceptance Switch fisik,
transisi native extra time/penalti atau kehilangan daya saat penulisan SD.
