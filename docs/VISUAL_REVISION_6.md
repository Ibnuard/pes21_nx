# Visual revision 6 — 31 Agustus 2026

**Digantikan v7 balanced:** lihat [VISUAL_REVISION_7.md](VISUAL_REVISION_7.md).
Tes Switch v6 mengonfirmasi clock tampil, tetapi urutan accent/logo salah dan
seam lapangan masih terang-terang. Interpretasi UV di bawah adalah hipotesis
historis yang belum tervalidasi, bukan hasil final.

Arsip kandidat berada di `local-debug/visual-v6-20260831/install/`. V6 hanya
mengubah PAK visual lapangan dan member UI scoreboard dalam OBB. NRO, kontrol,
roster, statistik, portrait, serta SaveData tidak berubah.

## Scoreboard

V5 membuktikan kompensasi scale 96x benar: plate sudah compact. Clock tidak
terlihat karena node clock stock berada pada depth 14/33, sedangkan background
custom opaque berada pada depth 60. Jadi clock sebenarnya tetap berjalan tetapi
tertutup oleh plate.

V6 mempertahankan seluruh frame/update clock dan hanya memindahkan kedua state
clock ke depth kosong 77/78, di atas background dan di bawah batas UI lain.
Posisinya menjadi x262.65. Atlas ujung kanan juga diurutkan ulang menjadi:

`[accent] [nama tim] [score] [nama tim] [accent EF10] [timer]`

Nama tim tetap kuning di navy, score navy di kotak kuning, dan digit timer navy
di field kuning. AS3, binding waktu/skor, string, virtual image size, fade, serta
tujuh movie UI lain tidak diubah.

## Lapangan

Audit material stock memberi jawaban pasti atas perilaku reverse. Material
`MI_Pitch_Low_R` tidak mengikat `pitch_r_bsm_alp`; ia mengikat
`pitch_l_bsm_alp` yang sama dengan sisi kiri, lalu membalik rect tersebut lewat
static switch `isL`. Rect lapangan aktif pada texture kiri adalah x254..1023,
bukan seluruh x0..1023.

V4 membuat kedua ujung rect aktif gelap, sehingga runtime gelap-gelap. V5
menyamakan kedua edge atlas menjadi terang, tetapi x254 dan x1023 tetap jatuh
pada shade terang di perangkat. V6 mengarang enam band tepat di rect aktif:

- x254 pada sisi kanan hasil mirror = gelap;
- x1023 pada sisi kiri = terang;
- texture kanan memakai rect x0..769 dengan fase yang sama;
- texture gabungan jauh memakai 12 band pada rect x127..896, dengan boundary
  terang-gelap tepat di x511/512.

Ini tidak menambah correction strip di tengah dan tidak memodifikasi material.
Warna serta grain sama dengan v5: `(26,46,12)` / `(49,77,23)` dan gain grain
RGB `(2.4,4.8,1.8)`.

## Instalasi

Tutup game dan backup file lama. Salin hanya dua file berikut:

| Sumber | Tujuan SD |
| --- | --- |
| `local-debug/visual-v6-20260831/install/PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `local-debug/visual-v6-20260831/install/patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

NRO tidak diganti. Jangan menyimpan PAK visual versi lama berdampingan dengan
nama lain. Uji timer sejak kickoff, update skor, added time, half/full-time,
serta seam lapangan pada kamera gameplay, replay, dan LOD jauh.

## Validasi host

- PAK dibuka ulang: 19 file, delapan texture, 37 mip, lima pemeriksaan grain,
  lima active-rect phase, alpha, metadata, dan blok garis lulus.
- Score member 98,239 byte di dalam slot 102,400 byte. Sebanyak 534 placement,
  58 record clock-depth, 17 scale plate, tint/fade teks, atlas, AS3, string, dan
  binding diperiksa.
- OBB tetap 1,391,120,384 byte; 421 member dt210 dan 23 member OBB lainnya
  byte-identical. Data tim/pemain tidak berubah.
- Hasil host valid; render v6 masih perlu dikonfirmasi di Switch.
