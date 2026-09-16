# Visual revision 2 — ditolak pada uji perangkat

Scoreboard memanjang dan lapangan terlalu smooth pada uji Switch. Gunakan
[VISUAL_REVISION_3.md](VISUAL_REVISION_3.md). Dokumen ini disimpan sebagai
riwayat teknis kandidat v2, bukan panduan instalasi aktif.

Kandidat tes terpisah di `local-debug/visual-v2-20260831/install/`.
**Bukan rilis stable; hasil render belum diuji di Switch.** Baseline yang sudah
disetujui di `local-debug/visual-baseline-20260831/` tidak ditimpa. Tidak ada
build/perubahan NRO, kamera, frame loop, controller, atau roster pada revisi ini.

## Lapangan

- Dua mask native `pitch_specular_mask_l/r` ikut dipatch. Kanal R/G yang berisi
  strip silang dinetralkan ke 128; B dan alpha dipertahankan byte-identical.
  Ini menguji hipotesis sumber overlap, bukan klaim bahwa semua layer material
  sudah diketahui. Alpha detail native masih dapat menyumbang variasi lain.
- Shade diffuse diperkuat: RGB gelap/terang dari `(30,51,13)/(46,72,22)` menjadi
  `(26,46,12)/(49,77,23)`. Selisih kanal hijau naik dari 21 ke 31, rata-rata tetap
  61.5. Jadi kontras pita tidak diperkuat dengan menambah grain atau sekadar
  menggelapkan seluruh lapangan. Nilai ini adalah texture-space, bukan janji
  warna akhir setelah lighting game.
- Seluruh texture detail/grain identik dengan baseline. Mesh, material, UV,
  format, ukuran mip, alpha, header, serta blok ETC1 garis native dipertahankan.
- Hasil: 19 file, 8 tekstur, 37 mip tervalidasi setelah PAK dibuka ulang.
  Sepuluh mip diffuse terkecil tetap stock karena seluruh bloknya termasuk
  perlindungan garis; ini disengaja.

Varian `ab-mask-only/` berisi PAK pembanding: keenam tekstur baseline persis sama,
hanya dua mask tambahan berubah. Gunakan jika perlu memisahkan pengaruh mask
dari shade baru. Varian ini menggantikan PAK utama, **jangan dimuat bersamaan**.

## Scoreboard

- Mengubah timeline native menjadi susunan satu baris: nama home, skor home,
  skor away, nama away, waktu, logo eFootball. Semua keyframe posisi yang
  relevan ikut digeser; elemen tambahan waktu/kartu/aggregate tetap disediakan.
- Palette navy/kuning dan logo diambil dari asset MatchTime EF10 milik pengguna.
  Jam memakai pelat kuning dengan glyph navy; dua skor memakai pelat navy
  berbingkai kuning. Ukuran atlas tetap 1024×512 ARGB8888, tidak menambah atlas.
- **Teks nama dan skor tetap putih native.** Audit menemukan flag color-update
  tanpa payload pada ujung animasi yang mengembalikan warna default. Recolor
  fade saja akan kembali putih saat permainan berjalan, sehingga kotak skor
  tidak dibuat kuning penuh. Mengubah FontColor komponen secara persisten
  merupakan pekerjaan lanjutan, bukan patch instruksi AS3 yang belum dipahami.
- Logo PES kecil pada scoreboard disembunyikan lewat instance lokal; shared
  texture logo di UI lain tidak diubah. Badge kompetisi EF10 belum diport.
- AP2 movie tetap 26,460 byte, 534 placement diperiksa, 167 field timeline
  berubah. AS3, binding, string, label, durasi, virtual dimensions gambar,
  dan tujuh movie lain tidak berubah. Alpha/RGB teks native serta reset/fade
  tetap utuh. Satu region background dipindahkan ke ruang atlas kosong.
- WESYS tetap format asli, dua tingkat kompresi lossless; member akhir 101,521
  byte, muat dalam slot CPK 102,400 byte. OBB tetap 1,391,120,384 byte. Tidak
  membutuhkan perubahan whitelist ukuran OBB di NRO.

Ini adaptasi asset/layout native PES21, **belum replika penuh UI EF10**.
Skala region, clipping, serta penempatan saat animasi tetap perlu diuji di game.

Format AP2/byteswap diteliti dengan pembanding source primer
[bemaniutils AFP parser](https://github.com/DragonMinded/bemaniutils/blob/master/bemani/format/afp/swf.py).
Parser lokal dibatasi ke hash/schema PES21 yang diaudit, termasuk image record
v11 dengan dimensi eksplisit; bukan parser AFP umum.

## Pemasangan dan tes

Tutup game, backup kedua file lama, lalu salin **hanya dua file di `install/`**:

| File | Tujuan SD |
| --- | --- |
| `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

NRO tetap yang sedang diuji dari `stability-test-20260830`. Jangan salin folder
build/verify/cpk, `.bin`, atau varian mask-only bersama PAK utama. Tidak perlu
mengganti `libUE4.so`, main PAK, Download, respons, atau SaveData.

1. Uji PAK dahulu dengan OBB lama: stadion/kamera/lighting yang sama dengan
   baseline, kickoff, garis gawang/tengah, replay dekat/jauh, dan siang/malam.
   Periksa apakah streak/kotak overlap berkurang dan grain tetap sesuai.
2. Tambahkan OBB scoreboard: pastikan boot, jam berjalan, gol memperbarui skor,
   nama tim terbaca, tambahan waktu, pause/replay, half-time/full-time, dan
   animasi masuk/keluar tidak membuat angka/logo menumpuk atau hilang.
3. Tetap lanjutkan tes 2–3 pertandingan berurutan; revisi visual ini tidak
   menyimpulkan status fix crash pertandingan kedua atau efektivitas FriendPress.

Rollback per file: PAK dari `visual-baseline-20260831/`, OBB dari
`stability-test-20260830/`. Keduanya tetap utuh. Jangan menghapus SaveData.

## Validasi dan reproduksi

Tujuh unit test synthetic, validasi 37 mip/garis/alpha, dan validasi seluruh
prefix non-atlas serta 25 region scoreboard lulus. Pengemasan membandingkan
421 member dt210 lain serta 23 member OBB lain byte-for-byte: roster/stat/foto
tidak berubah. Tidak ada eksekusi game asli dalam validasi host ini.

Input game tidak disertakan di Git; gunakan ekstraksi milik sendiri. Output
tetap di `local-debug/` yang di-ignore. Dependensi tambahan Zopfli hanya untuk
build lossless offline, tidak dibawa/dijalankan di Switch.

```powershell
python -m pip install -r tools/visual-patch-requirements.txt
python tools/build_efootball10_visual_patch.py --only pitch --pitch-style clean-v2 --pes21 local-debug/stability-visuals/verified-stock --output local-debug/visual-rebuild/pitch
python tools/build_efootball10_scoreboard_v2.py --output local-debug/visual-rebuild/score
repak pack --version V8A --compression Zlib local-debug/visual-rebuild/pitch/pitch-stage local-debug/visual-rebuild/PesMobile-Android_ETC1_P.pak
python tools/validate_efootball10_visual_patch.py --pitch-only --pitch-style clean-v2 --stock local-debug/stability-visuals/verified-stock --built local-debug/visual-rebuild/pitch/pitch-stage --baseline-pitch local-debug/stability-visuals/verify-packed
python tools/validate_efootball10_scoreboard_v2.py --candidate local-debug/visual-rebuild/score/game2dPes.bin
python tools/prepare_visual_test_bundle.py --base-obb local-debug/stability-test-20260830/patch.305030001.jp.nyan2021.pesam.obb --skin local-debug/visual-rebuild/score/game2dPes.bin --output local-debug/visual-rebuild/patch.305030001.jp.nyan2021.pesam.obb --work local-debug/visual-rebuild/cpk
python -m unittest discover -s tests -p 'test_*.py' -v
```

Untuk pembanding A/B, gunakan `--pitch-style mask-only` dengan output baru.
Builder revisi baru menolak folder output yang sudah ada.
