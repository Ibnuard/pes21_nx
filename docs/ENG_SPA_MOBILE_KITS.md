# Kits liga Inggris dan Spanyol: kandidat semua klub

## Konfirmasi terbaru (2026-09-09)

User mengonfirmasi "oke aman" setelah mencoba NRO production size-fix v1,
lalu meminta commit/push. Ini konfirmasi hasil tes user, bukan bukti bahwa
seluruh 39 klub dan semua varian kits telah diuji satu per satu. Catatan kandidat
di bawah menjelaskan status saat paket pertama dibangun.

Pasangan yang dikonfirmasi:

- OBB: 1401395200 byte, SHA-256
  `b8d43077586e5459d13bc8ac20d911acff732c0c455cbdc3cbf1a02e77a0c53a`.
- NRO production `ENG-SPA size-fix v1`: 46715085 byte, SHA-256
  `d3d6ed6fa9dddbced858e4a541b28c1b7392cd82378f4d154702013cfdc5589a`.
- Lokasi pasangan: `local-debug/eng-spa-all-kits-v3/`. Dist recovery sebelumnya
  tetap dipertahankan. Binary lokal tidak masuk Git; commit menyimpan tool,
  source size-fix, tes, dan dokumentasi.

## Cakupan

Basis: pasangan OBB/NRO `native-license-v7-madrid-preserve-order` yang sudah
dikonfirmasi stable di hardware. Dist stable tidak ditimpa.

Output kandidat: `local-debug/eng-spa-all-kits-v3/`.

- 37 klub tambahan: home, away, goalkeeper (111 kits / 222 tekstur mobile).
- Barcelona dan Real Madrid: seluruh tekstur dan descriptor stable dipertahankan
  byte-identik, sehingga total 39 klub native tercakup.
- Sunderland (396): tiga kits dikonversi di `converted/396`, tetapi tidak
  dimasukkan ke runtime karena Team.bin belum mempunyai slot tersebut. Penambahan
  klub/roster/assignment bukan bagian dari migrasi kits ini.
- Sumber: Football Life 2026 lokal, prioritas dt34 lalu season a, b, c; provenance
  dan hash setiap sumber ada dalam `asset-report.json`.
- Belum diuji di hardware. Jangan menandai kandidat ini stable sebelum tes manual.

## Cara menjalankan ulang

Gunakan output baru, jangan folder dist:

```powershell
python tools/build_eng_spa_mobile_kits.py --output local-debug/eng-spa-new-candidate
python -m unittest discover -s tests -p test_eng_spa_mobile_kits.py
```

Tool menggunakan dist stable sebagai dasar secara default. Opsi `--base-obb`
dan `--base-nro` memilih basis eksplisit; `--assets-only` hanya menyiapkan aset.
Tes integrasi lokal saat ini merujuk fixture v3; jika menguji kandidat lain,
sesuaikan fixture tes tersebut secara eksplisit. Tanpa fixture, tes integrasi
di-skip; tes fungsi descriptor tetap berjalan.

## Aturan tambahan setelah migrasi Madrid

1. Pertahankan descriptor realUni native jika sudah ada. Untuk slot generic,
   tambahkan descriptor PC 120-byte sebagai member realUni baru; jangan overwrite
   descriptor generic 96-byte. Normalisasi empat referensi tekstur ke nama mobile
   unik per tim/kit, tanpa mengubah parameter lain dalam descriptor PC.
2. Baca referensi body dan back dari descriptor PC, bukan menebak semuanya
   `uXXXXp1_back`. Klub Inggris memakai font bersama seperti `epl_whi_back`.
   Konversikan font tersebut ke nama yang diminta descriptor native.
3. Font EPL tersedia pada 4096x512 maupun 2048x256: keduanya atlas 8:1, diubah
   menjadi RGBA 320x40. Body 2048x2048 menjadi paletted PNG 256x384 dengan
   transform Uniform16 yang sama. Ukuran/layout lain ditolak untuk diperiksa.
4. Tolak konflik bila dua kits meminta member mobile yang sama tetapi isinya
   berbeda. Jangan mengubah tekstur font global diam-diam.
5. Untuk klub yang baru diaktifkan flag kits-nya, tambahkan alias crest `_r`
   dari varian `_f` yang sudah ada bila diperlukan. Klub yang sudah licensed
   tidak dinormalisasi nama crest-nya; misalnya Manchester United mempunyai
   varian `_r_b` dan `_r_w`. Semua crest existing tetap byte-identik.
6. Urutan TOC existing dan ID dipertahankan. Member baru ditambahkan di akhir,
   `Sorted=0` diterapkan pada arsip hasil. Semua payload di luar rencana divalidasi.
7. Basis Team.bin tetap milik paket stable. Hanya byte flag kits (offset 84
   tiap record) yang boleh berubah; jangan mengganti roster, player, face, atau
   tactics dengan data sumber Football Life.

Lihat [panduan stable](KITS_LOGOS_STABLE_MIGRATION.md) untuk latar belakang
regresi blackscreen, kits putih, pause dan selebrasi.

## Pengemasan dan NRO

Ukuran OBB v3: `1401395200` byte, SHA-256:
`b8d43077586e5459d13bc8ac20d911acff732c0c455cbdc3cbf1a02e77a0c53a`.
Penambahan member melampaui padding slot; outer OBB direpack dengan urutan
TOC/metadata non-payload dipertahankan. Ada 21 arsip luar yang payload-nya
byte-identik. Perubahan hanya dt120, dt200 dan dt240.

NRO stable lama tidak menerima ukuran baru ini. Allowance eksplisit ditambahkan
di `source/main.c`; build production dilakukan tanpa `-Diagnostics`:

```powershell
.\build-wsl.ps1 -OutputDirectory local-debug/eng-spa-all-kits-v3/production -Jobs 8
```

Build memakai working source saat ini, bukan rekonstruksi bit-identik NRO stable
lama. Karena itu NRO baru dan repack OBB harus dites sebagai satu pasangan.

### NRO size-fix v1

Setelah laporan validasi loose-file, ukuran aktual OBB diperiksa ulang:
`1401395200` byte. Ukuran ini sudah diizinkan source kandidat sebelumnya, jadi
penyebab laporan belum terbukti hanya mismatch allowance. Build production
`nro-size-fix-v1/pes21_nx.nro` menjadikan ukuran itu acuan utama dan menampilkan
nama file, actual bytes, expected/current bytes serta penanda `ENG-SPA size-fix v1`
di layar kegagalan (tanpa mengaktifkan debug.log). Ukuran recovery lama tetap
diizinkan; file hilang atau ukuran sembarang tetap ditolak. Bila masih gagal,
kirim foto layar lengkap, jangan mematikan seluruh validasi runtime.

## Tes manual sebelum promosi

Ganti OBB dan NRO sebagai pasangan; jangan campur NRO stable lama. File runtime
lain tetap dari instalasi yang sudah berjalan. Tes boot/menu, home/away/GK,
Game Plan, goal celebration A, skip B, pause/resume dan restart pertandingan.
Mulai dari Arsenal vs Chelsea dan Atletico vs Sevilla, lalu ulangi Madrid vs
Barcelona sebagai tes regresi. Periksa juga tim lainnya dan kit away/GK sebelum
menganggap cakupan semua klub telah terverifikasi.

Jika ada regresi, pulihkan pasangan di `dist/pes21_nx/` dan laporkan tim, varian
kits, serta langkah pemicu. Candidate ini tidak otomatis di-commit/push ataupun
dipromosikan ke stable.
