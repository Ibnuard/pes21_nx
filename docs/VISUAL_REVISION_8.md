# Visual v8 — Low material phase + scoreboard alignment

**Baseline visual stable, dikonfirmasi pengguna di Switch pada 31 Agustus 2026:**
scoreboard sudah oke dan midpoint lapangan sudah selang-seling. Paket v8 di
`local-debug/visual-v8-20260831/install/` dipertahankan sebagai rollback untuk
iterasi berikutnya. Konfirmasi ini mencakup visual, bukan audit seluruh mode
atau jaminan stabilitas pertandingan berulang. NRO, roster, portrait, controller dan setting
grafis tidak diubah. Tetap gunakan Standard/Low, tidak perlu mengaktifkan High.

## Penyebab lapangan mirror yang terbukti dari shader

Hasil Switch v7 masih terang-terang di tengah meskipun edge PNG berbeda.
Audit ini membaca shader GLSL yang dikompresi di material cooked, bukan hanya
melihat nama texture atau UV0 mesh:

- Parent Low kiri membaca diffuse dengan UV `(u, v)`.
- Kedua instance Low kanan (`MI_Pitch_Low_R` dan
  `MI_Pitch_Default_night_Low_R`) mempunyai 80 pixel shader yang semuanya
  mengalikan UV diffuse dengan `(-1, 1)`.
- Kedua sisi mewarisi texture `pitch_l_bsm_alp` yang sama. Dengan wrap sampler,
  sisi kanan dekat u=0 membaca ujung kanan texture yang juga dibaca sisi kiri.
  Ini menjelaskan hasil terang-terang dari patch PNG sebelumnya.

Mengubah phase PNG kanan biasa tidak berpengaruh pada binding tersebut.
Menghapus mirror juga akan mengubah mapping garis yang sudah benar.

V8 mempertahankan shader dan UV mirror, tetapi memisahkan binding warna:

| Jalur | Parent material | Diffuse |
| --- | --- | --- |
| Low kiri | `M_Pitch_Default_night_Low` asli | `pitch_l_bsm_alp` v7 |
| Low kanan (dua instance) | salinan `M_Pitch_Default_night_NXR` | `pitch_n_bsm_alp`, phase kebalikan |

Texture baru memakai **garis/koordinat texture kiri asli**, sehingga setelah
mirror garis tetap seperti sebelumnya. Hanya phase dua shade yang dibalik.
Warna `(26,46,12)` / `(49,77,23)` dan gain grain `(2.8,5.6,2.1)` tetap sama.
Seluruh 19 file texture baseline v7 di PAK tetap byte-identical.

Nama package/import diganti dengan nama berpanjang sama. Tool memeriksa bahwa
header hanya berbeda pada entry name-table yang diizinkan. Hash nama dibuat
melalui [CLI UAssetGUI](https://github.com/atenfyr/UAssetGUI#command-line-interface).
Export payload `.uexp`, termasuk shader compiled, disalin dari sumber asli;
hasil reserialisasi export dari UAssetGUI tidak digunakan. Tidak ada perubahan
shader bytecode, posisi mesh, alpha garis, NRO, atau material High.

Pemeriksa asset terpisah (UE Viewer) berhasil membuka Low_R → parent baru →
texture baru tanpa unresolved import. Ini validasi host; keberhasilan render
dan stabilitas Switch tetap harus dites, bukan disimpulkan dari preview PNG.

## Scoreboard

Proporsi v7 yang disetujui dipertahankan: box tim 78 px per sisi, skor 38 px,
timer 96 px, box logo 48×48 dan ikon 24×24. Urutan juga tidak berubah.

V7 menggambar separator x116..117 di dalam kotak skor kanan saja. Akibatnya
kuning yang terlihat berukuran 38 px di kiri, 37 px di kanan. V8 menggambar
separator x115..117, mengambil satu pixel dari masing-masing kotak: area
kuning kini sama-sama 37 px.

Teks tim dan skor digeser 2 px ke kiri untuk koreksi optical alignment dari
screenshot v7. Ini koreksi posisi semua keyframe, bukan pengecilan font atau
perubahan box. Timer, logo, scale teks, warna, AS3 dan binding tetap sama.
Periksa lagi centering di Switch, termasuk skor berubah menjadi 1/2 digit.

## File yang disalin

Tutup game sepenuhnya dan backup file lama. Timpa **dua file**:

| Sumber dalam `install/` | Tujuan SD |
| --- | --- |
| `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

NRO tidak diganti. Jangan menambahkan PAK lama dengan nama lain, menyalin
file material satu per satu, folder build, JSON, atau SaveData. Jalankan ulang
game agar material baru dimuat. Rollback memakai kedua file dari v7.

## Hasil validasi host

- 12 unit test lulus.
- PAK dibuka ulang: 27 file, termasuk 19 file baseline yang identik.
- Ketiga payload material/shader identik dengan sumbernya; hanya name-table
  header yang berubah. Satu diffuse baru mempertahankan 1.809 blok garis.
- Sampel warna kanan berlawanan dengan kiri (korelasi -0,9992); bukan
  menambahkan strip sempit di tengah.
- Scoreboard 98.474 byte, muat dalam slot 102.400 byte. Member yang dibaca
  kembali langsung dari OBB identik dengan hasil build.
- OBB tetap 1.391.120.384 byte; 421 member CPK dan 23 member OBB lainnya
  byte-identical. Roster dan portrait tetap utuh.

Hasil Switch: scoreboard dan alternasi midpoint sudah disetujui. Permintaan
selanjutnya adalah merapikan lebar strip secara seragam di seluruh lapangan,
bukan meregangkan strip khusus di kotak penalti. V8 tetap baseline yang utuh.

## Reproduksi

Gunakan direktori output baru. Baseline v7 dan asset original tetap diperlukan.

```powershell
python -m unittest discover -s tests -v
python tools/build_low_pitch_phase_patch.py --output local-debug/rebuild-v8/pitch
python tools/validate_low_pitch_phase_patch.py --built local-debug/rebuild-v8/pitch/pitch-stage
python tools/build_efootball10_scoreboard_v2.py --output local-debug/rebuild-v8/score
python tools/validate_efootball10_scoreboard_v2.py --candidate local-debug/rebuild-v8/score/game2dPes.bin
repak pack --version V8A --compression Zlib local-debug/rebuild-v8/pitch/pitch-stage local-debug/rebuild-v8/PesMobile-Android_ETC1_P.pak
python tools/prepare_visual_test_bundle.py --skin local-debug/rebuild-v8/score/game2dPes.bin --output local-debug/rebuild-v8/patch.305030001.jp.nyan2021.pesam.obb --work local-debug/rebuild-v8/cpk
```
