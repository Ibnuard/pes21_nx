# Visual revision 5 — digantikan v6

Hasil Switch: lebar scoreboard sudah benar, tetapi timer tertutup background
opaque dan accent kanan berada setelah timer. Pitch masih terang-terang karena
Low_R memirror rect aktif dari texture kiri, bukan memakai edge PNG yang telah
dinormalisasi v5. Gunakan [VISUAL_REVISION_6.md](VISUAL_REVISION_6.md).

Kandidat aktif berada di `local-debug/visual-v5-20260831/install/`. V5 tidak
mengubah NRO, kontrol, roster, statistik, portrait, SaveData, material, mesh,
atau UV. Perubahan hanya pada dua file visual yang memang diuji.

## Scoreboard

Penyebab bar v4 memanjang adalah perbedaan ukuran region atlas fisik. Region
native hanya 4 px dan dianimasikan sekitar 96x; region custom menjadi 384 px.
Karena itu 17 keyframe scale-X background sekarang dibagi **96**, bukan tiga.
Rentang scale hasilnya sekitar `0.85..1.00`, sehingga target plate kembali
sekitar 384 px dan tidak lagi sengaja dipotong oleh viewport.

Warna mengikuti referensi:

- area nama tim navy dengan teks kuning `(230,230,0)`;
- dua kotak skor solid kuning dengan angka navy `(0,0,100)`;
- field waktu kuning dengan digit navy;
- logo EF10 tetap di ujung kanan; badge kompetisi belum diport.

Tint nama/skor diterapkan pada record warna timeline native. Record endpoint
yang sebelumnya mereset tint ke putih hanya kehilangan flag reset warnanya;
fade, frame, transform, binding, string, dan AS3 tetap native. Tujuh UI movie
lain tidak berubah.

## Lapangan

Sistem pitch memiliki tiga jalur yang harus konsisten: texture kiri dan kanan
untuk LOD normal/exLow, serta texture gabungan `pitch_lr` untuk LOD jauh. Jadi
ini bukan satu PNG yang cukup di-reverse. V4 memberi offset setengah band pada
semuanya; di perangkat hasilnya menjadi shade gelap yang melintasi marking.

V5 menghapus offset tersebut dan mengarang pattern dari seam native:

- sisi kiri yang menempel garis tengah selalu shade terang;
- sisi kanan yang menempel garis tengah selalu shade gelap;
- texture gabungan berganti shade tepat di x tengahnya;
- edge cadangan pada texture half dinormalisasi agar orientasi UV tidak dapat
  menghasilkan terang-terang lagi.

Tidak ada strip gelap khusus yang ditambahkan di tengah. Target dua warna tetap
`(26,46,12)` dan `(49,77,23)`. Grain high-frequency EF10 dinaikkan 20% dari v4,
dari gain RGB `(2.0,4.0,1.5)` menjadi `(2.4,4.8,1.8)`. Residual broad/mid
frequency yang menimbulkan tile burik tetap dibuang.

Seluruh 37 mip dari delapan texture dibangun dan diperiksa. Alpha, header,
ukuran payload, format, dan blok ETC1 yang mengandung garis asli dipertahankan.

## Instalasi

Tutup game dan backup file lama. Salin hanya dua file berikut:

| Sumber | Tujuan SD |
| --- | --- |
| `local-debug/visual-v5-20260831/install/PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `local-debug/visual-v5-20260831/install/patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

Jangan mengganti NRO dan jangan menyimpan PAK visual lama dengan nama lain di
folder `Paks`. Uji kickoff, update skor, added time, half/full-time, kamera
gameplay dan replay, garis tengah, garis gawang, serta transisi LOD.

## Validasi host

- PAK: 19 file, delapan texture, 37 mip; lima pemeriksaan grain dan lima seam
  lolos setelah PAK dibuka ulang.
- Score member: 101,536 byte, masih di bawah slot 102,400 byte; 534 placement,
  17 scale background, tint/fade teks, region atlas, AS3, string, dan binding
  diperiksa.
- OBB tetap 1,391,120,384 byte. Sebanyak 421 member dt210 dan 23 member OBB
  lainnya byte-identical; data tim/pemain tidak berubah.
- Ini lolos validasi host, tetapi hasil render v5 masih perlu dikonfirmasi pada
  Switch.
