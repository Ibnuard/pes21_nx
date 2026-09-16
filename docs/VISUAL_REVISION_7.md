# Visual v7 — scoreboard proporsional, kandidat tes Switch

Status perangkat: proporsi scoreboard disetujui, tetapi centering teks dan
seam lapangan perlu koreksi. Kandidat terbaru: [VISUAL_REVISION_8.md](VISUAL_REVISION_8.md).

Paket terbaru ada di `local-debug/visual-v7-20260831/install/`.
Gunakan versi **balanced** ini, bukan `score-build/` atau
`superseded-pre-proportion/`. NRO dan isi `dist/` tidak ditimpa.

## Scoreboard

Urutan yang ditargetkan:

`[accent][tim][score][tim][accent][waktu][logo PES]`

Box nama tim kiri/kanan sekarang sama lebar dan memakai scale serta padding
teks yang sama. Dua kotak skor juga sama lebar. Logo di ujung kanan mendapat
box persegi, bukan strip vertikal.

| Elemen | Lebar × tinggi, pixel atlas |
| --- | --- |
| Nama tim kiri | 78 × 48 |
| Skor kiri | 38 × 48 |
| Skor kanan | 38 × 48 |
| Nama tim kanan | 78 × 48 |
| Accent kanan native | 8 × 48 |
| Waktu | 96 × 48 |
| Box logo PES | 48 × 48 |

Ikon logo tetap 24 × 24, di tengah box dengan padding 12 pixel pada keempat
sisi. Main plate tetap 384 × 48; accent kiri native berada di luar plate itu.
Ukuran di layar mengikuti scale global UI game.

Audit ulang menemukan accent native tersusun dari dua tile **8 × 24**, bukan
24 × 48. Child offset x=-2 dan mirror pada parent kanan diperhitungkan: anchor
kanan x244 menghasilkan accent x238..246, di antara box tim dan clock.
Nama tim berpindah ke x8 / x162; clock ke x236.65 agar isi digit berada di
tengah field kuning x246..342. Layout digit menit satu, dua, dan tiga angka
tetap mengikuti timeline native.

Perbaikan yang sudah berhasil di perangkat tetap dipakai: kompensasi scale
plate 96×, clock depth 77/78, teks tim kuning, angka skor/waktu navy.
AS3, string, binding waktu/skor, fade native, serta tujuh movie UI lain tidak
diubah. Box dan posisi sekarang berasal dari satu recipe
`tools/scoreboard_geometry.py` dan diperiksa unit test.

## Lapangan: status masih kandidat

PAK v7 dari iterasi sebelumnya dipertahankan pada koreksi proporsi ini.
Warna dasar tetap `(26,46,12)` / `(49,77,23)`; grain diffuse memakai gain
`(2.8,5.6,2.1)`. Pola dibuat enam strip di seluruh texture satu sisi dan
dua belas strip pada texture gabungan. Edge diffuse dibuat berbeda shade;
garis asli, alpha, header dan format tetap dijaga.

Yang terbukti dari audit file: material Low kiri/kanan berbagi texture kiri;
mesh yang diekspor memiliki UV0 seam kiri u=1 dan kanan sekitar u=0.
**Itu belum membuktikan UV akhir setelah shader di Switch.** Asumsi v6 bahwa
`isL` pasti membalik rect x254..1023 terbukti belum cukup dari hasil perangkat.
Jadi preview texture yang sudah selang-seling bukan bukti seam in-game telah
beres. V7 masih perlu tes Switch; jika masih mirror, jangan mengulang klaim
bahwa mengubah PNG saja sudah menyelesaikan jalur material tersebut.

## Salin ke Switch

Tutup game. Backup kedua file lama, lalu timpa hanya dua file berikut:

| Dari folder `install/` | Tujuan SD |
| --- | --- |
| `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |
| `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |

NRO tetap yang saat ini sudah berjalan baik. Jangan menyalin `game2dPes.bin`
secara terpisah, folder build/cpk/verify, JSON validasi, atau SaveData.
Jangan memasang beberapa PAK visual dengan nama berbeda secara bersamaan.

## Validasi dan tes perangkat

Scoreboard balanced berukuran 97,519 byte, di bawah slot 102,400 byte.
Pemeriksaan mencakup 534 placement, 17 keyframe scale plate, 58 record clock,
kesetaraan box tim/skor, margin logo, warna/fade teks, serta container UI.
PAK dibuka ulang: 19 file, 8 texture, 37 mip; alpha, metadata dan blok garis
native lulus pemeriksaan. Ukuran OBB tetap 1,391,120,384 byte.

Manifest dan laporan package berada di folder revisi. Validasi host tidak
menjamin hasil render atau stabilitas perangkat.

Tes utama: kickoff dengan inisial tim kiri/kanan sama panjang, update skor,
menit 1/2/3 digit (termasuk extra time jika dimainkan), added time, serta
logo persegi. Untuk lapangan, periksa kedua sisi garis tengah pada gameplay
dan replay. Roster, portrait, controller, helper, frame pacing dan NRO tidak
diubah oleh paket ini.

## Reproduksi

Gunakan direktori output baru agar tidak menimpa kandidat sebelumnya.

```powershell
python -m unittest discover -s tests -v
python tools/build_efootball10_scoreboard_v2.py --output local-debug/rebuild-v7/score
python tools/validate_efootball10_scoreboard_v2.py --candidate local-debug/rebuild-v7/score/game2dPes.bin
python tools/build_efootball10_visual_patch.py --pitch-style clean-v7 --only pitch --output local-debug/rebuild-v7/pitch
repak pack --version V8A --compression Zlib local-debug/rebuild-v7/pitch/pitch-stage local-debug/rebuild-v7/PesMobile-Android_ETC1_P.pak
python tools/prepare_visual_test_bundle.py --skin local-debug/rebuild-v7/score/game2dPes.bin --output local-debug/rebuild-v7/patch.305030001.jp.nyan2021.pesam.obb --work local-debug/rebuild-v7/cpk
```
