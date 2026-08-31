# Visual revision 3 — digantikan v4

Hasil perangkat tersedia: grain mulai terasa tetapi masih kurang, midfield
masih satu band terang, dan rollback scoreboard tidak dipertahankan. Gunakan
[VISUAL_REVISION_4.md](VISUAL_REVISION_4.md). Dokumen ini menjadi riwayat v3.

Kandidat tes di `local-debug/visual-v3-20260831/install/`. Revisi ini menanggapi
hasil Switch v2: background scoreboard memanjang, grain rumput terlalu lemah,
dan dua band di sambungan tengah mempunyai shade sama.

## Perubahan

- Warna dan besar kontras strip v2 dipertahankan: RGB target tetap
  `(26,46,12)` dan `(49,77,23)`.
- Grain high-frequency dari crop rumput EF10 sekarang ikut dibake langsung ke
  lima diffuse PES21 dengan gain RGB `(1.6,3.2,1.2)`. Rata-rata hijau hasil
  decode berbeda kurang dari 0.5 level terhadap v2; jadi ini menambah detail,
  bukan mengubah shade. Residual mid-frequency ditolak karena preview audit
  memperlihatkan pola kotak/baked tile.
- Fase dua texture half-pitch kanan dibalik. Game memirror half kanan dan pada
  hasil perangkat v2 kedua band yang bertemu di tengah menjadi terang–terang;
  v3 mengarang fase berlawanan. Texture full-pitch exLow tetap satu urutan
  kontinu dan tidak dibalik.
- Mask pantulan v2, seluruh 10 mip detail lama, B/alpha mask, UV, material,
  mesh, header, ukuran mip, serta blok ETC1 yang mengandung garis tetap sama.
- Eksperimen scoreboard single-row dibatalkan. OBB v3 byte-identical dengan
  baseline compact `stability-test-20260830`, sehingga background kembali ke
  geometri/animasi native yang sebelumnya tampil benar. Port single-row perlu
  desain ulang dari transform native dan tidak dipaksakan pada kandidat ini.

Tidak ada NRO baru; kamera, frame pacing, helper/controller, roster, statistik,
portrait, SaveData, dan file runtime lain tidak disentuh.

## Instalasi

Tutup game dan backup file lama, lalu salin hanya dua file dari
`local-debug/visual-v3-20260831/install/`:

| File | Tujuan SD |
| --- | --- |
| `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

OBB wajib ikut disalin untuk menghapus scoreboard v2 yang memanjang. NRO tidak
perlu diganti. Jangan gabungkan PAK v2/v3 dengan nama lain di folder Paks.

## Fokus tes

1. Pastikan scoreboard kembali compact seperti baseline, waktu/skor berjalan,
   dan animasi gol/added time/half-time tidak memanjang.
2. Gunakan stadion, kamera, dan lighting yang sama dengan screenshot v2.
   Pastikan pola/warna tidak berubah, tetapi grain rumput terlihat halus.
3. Di garis tengah, pastikan band kiri dan kanan bergantian gelap–terang, bukan
   terang–terang. Cek juga full-pitch pada replay jauh agar LOD tetap konsisten.
4. Periksa semua garis tengah/gawang/penalti, siang/malam, serta 2–3 match
   berurutan. Validasi host tidak menggantikan render dan stability test Switch.

Rollback lapangan menggunakan PAK `visual-v2-20260831/install/` bila perlu;
untuk kembali ke baseline penuh gunakan PAK `visual-baseline-20260831/`. OBB v3
sudah merupakan OBB baseline compact.

## Validasi host

- PAK dibuka ulang: 19 file, 8 tekstur, 37 mip.
- Header, format, ukuran payload, alpha, dan blok garis asli lulus pemeriksaan.
- Lima pemeriksaan grain menunjukkan variasi piksel halus lebih tinggi dari v2,
  sementara mean warna tetap; dua pemeriksaan half kanan mengonfirmasi korelasi
  fase berbalik di atas 0.98.
- OBB SHA256 identik dengan baseline compact; data seluruh tim tidak diubah.
- Belum diuji di perangkat setelah perubahan v3.
