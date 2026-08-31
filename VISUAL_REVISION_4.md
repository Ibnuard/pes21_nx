# Visual revision 4 — digantikan v5

Hasil perangkat: background scoreboard masih memenuhi viewport karena faktor
scale seharusnya 96, bukan 3. Offset setengah band juga membuat area gelap
melintasi garis tengah. Gunakan [VISUAL_REVISION_5.md](VISUAL_REVISION_5.md).
Dokumen di bawah dipertahankan sebagai riwayat v4.

Kandidat di `local-debug/visual-v4-20260831/install/`. V4 mempertahankan warna
lapangan yang diterima, menaikkan grain sedikit, menggeser **batas** strip agar
midfield bergantian, serta memperbaiki scoreboard single-row tanpa rollback.

## Lapangan

- Target warna tetap `(26,46,12)` dan `(49,77,23)` seperti v2/v3.
- Gain grain diffuse naik 25% dari `(1.6,3.2,1.2)` menjadi `(2.0,4.0,1.5)`.
  Grain tetap high-frequency EF10; residual mid-frequency yang membentuk kotak
  tidak dipakai.
- V3 hanya menukar warna/paritas half kanan, sehingga posisi batas mowing tidak
  berpindah dan midfield masih berada di tengah band terang. V4 menghapus trik
  itu dan memberi offset **setengah lebar band** ke kelima diffuse: 64 px untuk
  half-pitch dan 32 px untuk full-pitch exLow. Dengan begitu titik yang semula
  pusat band menjadi batas gelap–terang.
- Mask bersih v2, texture detail 10 mip, garis, alpha, format, UV, material, dan
  mesh tidak berubah. Seluruh 37 mip serta blok ETC1 garis diperiksa lagi.

## Scoreboard single-row

V2 memindahkan background dari region fisik 4 px ke 384 px, tetapi timeline
native masih mengalikan image virtual 6-unit sampai sekitar 96×. Karena seluruh
region baru opaque, bar terlihat sekitar 1152 px dan memanjang sampai tombol
pause.

V4 mempertahankan atlas single-row, palette, posisi nama/skor/waktu, dan logo
EF10. Hanya 17 keyframe scale-X `plateMain` dibagi tiga: rentang animasinya
sekarang sekitar 27.2–32×. Target lebar bar sekitar 384 px dan seluruh easing,
fade, added time, binding, strings, AS3 serta tujuh UI movie lain tetap native.

Nama dan skor masih putih native di atas navy; kotak skor berbingkai kuning,
jam kuning dengan digit navy. Badge kompetisi belum diport. Hasil ukuran,
clipping, waktu, dan logo tetap harus dikonfirmasi pada Switch.

## Instalasi

Tutup game, backup, lalu salin **dua file** dari
`local-debug/visual-v4-20260831/install/`:

| File | Tujuan SD |
| --- | --- |
| `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

NRO tidak diganti. Jangan menaruh PAK versi lain berdampingan dengan nama lain.

Fokus tes: grain pada kamera gameplay/replay, batas strip tepat di garis tengah,
LOD jauh, seluruh garis, lalu scoreboard saat kickoff/gol/added time/half-time.
Jika scoreboard masih salah, rollback OBB saja ke `stability-test-20260830`;
PAK v4 dapat tetap diuji terpisah. Rollback lapangan memakai PAK v3 atau baseline.

## Validasi host

- PAK dibuka ulang: 19 file, 8 tekstur, 37 mip; lima grain dan lima offset fase
  tervalidasi terhadap baseline.
- Score member 101,432 byte dan tetap muat pada slot 102,400 byte. Sebanyak 534
  placement diperiksa, termasuk 17 scale keyframe compact; AS3/string/binding,
  image virtual sizes, text fade/reset, dan tujuh movie lain tetap utuh.
- OBB tetap 1,391,120,384 byte; 421 member dt210 dan 23 member OBB lainnya
  byte-identical. Roster/stat/portrait tidak berubah.
- Belum ada render test Switch setelah build v4.
