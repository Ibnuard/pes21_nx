# Kandidat stabilitas + visual EF10 — 31 Agustus 2026

Baseline stable terbaru per 1 September 2026 adalah
[visual v14](VISUAL_REVISION_14.md), di
`local-debug/visual-v14-stable-20260901/install/`. Pitch v14 memakai koreksi
simetris hanya pada satu strip area gawang dan mempertahankan fase
selang-seling di tengah. Runtime-nya sengaja memakai kembali NRO visual v9 /
rilis v1.98 agar mapping, Player Cursor Show/Hide, opacity tombol action native,
warna helper, Press A, dan frame pacing stable tetap utuh.

Native Pad Lab v14 ditolak pada uji perangkat: match dapat dimulai tetapi
Joy-Con tidak mengontrol pemain, dan fitur runtime visual/controller stable
ikut hilang. NRO tersebut hanya diarsipkan untuk diagnosis dan bukan file
install. Detail hasil ada di [NATIVE_PAD_LAB_RESULT.md](NATIVE_PAD_LAB_RESULT.md).

Native Pad Lab V2 sudah diuji di Switch dan binary yang sama dipromosikan
menjadi **Native Mapping Baseline V1** di
`local-debug/native-pad-v1-baseline-20260901/install/`. Live-play dan kombinasi
R2, L1+X, serta L1+Segitiga sudah terkonfirmasi native. Power gauge visual serta
goal kick/corner/throw-in masih backlog karena konteks itu tetap memilih unit
mobile berbasis swipe. [Scope baseline](NATIVE_MAPPING_BASELINE_V1.md).

Kandidat lanjutan terpisah untuk goal kick tersedia sebagai **Native Setplay
V3** di `local-debug/native-setplay-v3-20260901/`. Kandidat ini memasang
SetplayGuide, ShortPass, LongPass, Shoot, dan GoalkickPassSupport native serta
menampilkan telemetry command langsung di layar; tidak menyintesis touch/swipe.
Statusnya baru host/ABI validated dan belum menggantikan baseline sampai lolos
uji Switch. [Checklist perangkat](NATIVE_SETPLAY_V3_TEST.md).

V3 kini disimpan sebagai arsip diagnosis. Kandidat aktif **Native Setplay V4**
berada di `local-debug/native-setplay-v4-20260901/`: LS masuk sebagai arah
tendangan dan RS masuk ke slot native camera stick, dengan route terpisah untuk
goal kick, corner, dan free kick. V4 tetap Lab-only dan belum menjadi baseline
sampai lolos perangkat. [Checklist V4](NATIVE_SETPLAY_V4_TEST.md).

Baseline pitch lama v10 tetap disimpan sebagai rollback historis di
`local-debug/visual-v10-20260831/install/`, tetapi sudah digantikan oleh v14.

Kandidat berikutnya harus dibangun terpisah dari v10. Fitur runtime
helper/cursor tetap dari [v9](VISUAL_REVISION_9.md).

Status: **siap uji perangkat, belum dinyatakan stable**. Paket terpisah di
`local-debug/stability-test-20260830/`; runtime yang sedang dipakai di `dist/`
tidak ditimpa. Multiplayer/2P tidak dikerjakan pada iterasi ini.

### Umpan balik perangkat: baseline visual lapangan

Pada 31 Agustus pengguna melaporkan tampilan lapangan sudah bagus dan meminta
versi ini dijadikan baseline. PAK persis beserta snapshot recipe disimpan di
`local-debug/visual-baseline-20260831/` (SHA256 `ec763228...7a7faa`). Bukan revisi
baru, sehingga tidak perlu menginstal ulang. Ini persetujuan **visual lapangan**,
bukan konfirmasi crash match kedua/FriendPress sudah terselesaikan.

Pola masih terlihat overlap. Audit lanjutan menemukan mask native
`pitch_specular_mask_l/r` yang tetap digunakan material dan belum dipatch:
kanal R/G-nya mengandung strip dua arah serta streak tipis. Ini kandidat kuat
pola yang bertumpuk dengan diffuse baru; perlu A/B perangkat sebelum menyatakan
akar masalah terkonfirmasi. Prioritas iterasi visual berikutnya adalah
menyamakan pola warna/pantulan, lalu menguatkan dua shade tanpa menambah noise.
Garis, UV, grain baseline, dan runtime tetap dijaga.

Scoreboard yang dituju mengikuti baris ringkas referensi EF10 dengan nama tim
kuning di navy dan skor/waktu navy di kotak kuning. Paket saat ini belum mengubah
geometri maupun warna teks native PES21. Layout tersebut membutuhkan pekerjaan
lanjutan pada UI, bukan sekadar recolor pelat.

## Perubahan

Iterasi visual lanjutan, tanpa NRO baru, tersedia di
[VISUAL_REVISION_2.md](VISUAL_REVISION_2.md). Penjelasan di bawah ini tetap
merujuk paket baseline `stability-test-20260830`, bukan mengganti riwayatnya.

Hasil perangkat menolak scoreboard/geometri v2 dan meminta grain serta fase
midfield diperbaiki. Kandidat penggantinya ada di
[VISUAL_REVISION_3.md](VISUAL_REVISION_3.md); v2 tidak lagi untuk dipasang.

Tes v3 meminta grain sedikit lebih kuat, boundary midfield benar-benar digeser,
dan single-row scoreboard diperbaiki. Kandidat aktif berikutnya adalah
[VISUAL_REVISION_4.md](VISUAL_REVISION_4.md).

Hasil Switch v4 menunjukkan kompensasi background scoreboard masih salah dan
offset setengah band membuat shade gelap memotong garis tengah. V5 memperbaiki
lebar plate, tetapi timer tertutup plate opaque dan mode Low_R masih membentuk
terang-terang. Kandidat aktif sekarang adalah
[VISUAL_REVISION_6.md](VISUAL_REVISION_6.md): clock dinaikkan pada display list,
accent dipindah sebelum timer, dan pattern di-anchor ke rect lapangan aktif yang
benar-benar dimirror oleh material Low_R.

1. **Retensi memori mmap.** Implementasi sebelumnya menahan seluruh alokasi
   sampai halaman terakhir dilepas. Contohnya UE4 dapat meminta 4 MiB, lalu
   menyisakan 4 KiB, tetapi backing 4 MiB tetap tertahan. Implementasi baru
   menggunakan backing 64 KiB yang dapat dilepas independen. Uji kasus tersebut
   sekarang menyisakan 64 KiB, lalu kembali nol setelah unmap terakhir. Memori
   dikembalikan ke allocator untuk dipakai ulang, bukan mengecilkan process heap.
   Ini memperbaiki retensi yang terbukti pada shim; hubungan dengan force-close
   pertandingan kedua masih perlu dikonfirmasi lewat uji Switch. `madvise`
   tetap no-op, jadi ini bukan klaim semua kemungkinan leak sudah terselesaikan.
2. **Prototype tahan Y saat defense → FriendPress native.** Hanya ThinkUnit
   FriendPress milik cursor lokal yang menerima input sementara. Mode offense,
   pause/menu, disconnect/timeout, dan pemain remote tidak diikutkan. History
   pad dikembalikan setelah pemanggilan. Ini *teammate/support pressure*, bukan
   jaminan fitur Match-up/jockey ala eFootball terbaru. Efektivitas di gameplay
   belum diuji di perangkat. Y saat offense tetap shoot; B/A/L/R tidak diganti.
3. **Skin pelat scoreboard EF10.** Warna navy/kuning diambil dari pelat MatchTime
   EF10 dan dibake ke empat region atlas native PES21. Bukan transplantasi widget
   UE4 EF10. Layout, tulisan putih, angka, logo PES, animasi/scripts, dan alpha
   native dipertahankan. Ini belum merupakan replika penuh scoreboard EF10.
4. **Pitch patch mencakup seluruh mip.** Enam tekstur, 35 mip diperiksa dan
   diproses; grain diambil dari channel rumput EF10, bukan mask RGB mentahnya.
   Termasuk tekstur detail bertile yang sebelumnya tidak ikut dipatch. Shade
   dua warna dipisahkan dari intensitas grain. Material, mesh, UV, format dan
   ukuran payload memakai PES21 asli. Blok ETC1 berisi garis asli dipertahankan,
   termasuk pada mip jauh; akibatnya 10 mip terkecil tetap identik karena semua
   bloknya termasuk area perlindungan garis. 25 mip lainnya berubah. Patch lama
   yang mengoverride MI_Pitch digantikan paket texture-only. Shader/lighting
   PES21 tetap aktif, sehingga hasilnya belum bisa dijanjikan persis referensi.

Koreksi audit sebelumnya: tiga tekstur diffuse yang dahulu dipatch masing-masing
memang hanya punya **satu mip**, bukan rantai mip tersembunyi. Rantai mip terdapat
di tekstur exLow kiri/kanan dan tekstur detail tambahan.

NRO kandidat dibangun dari snapshot `local-debug/v198-stable-player-build`
(basis v1.98 `99a0883`, ditambah perubahan roster/foto yang sudah diuji), dengan
patch mmap dan FriendPress di atas. Bukan rebuild seluruh eksperimen root tree.
`DIAGNOSTICS=0 PERF_TRACE=0`; tidak ada perubahan tracking kamera, loop render,
interval polling, atau helper overlay yang sudah ada. Ada snapshot statistik
mmap on-demand, tetapi tidak ada sampler/scan per frame.

## File yang dipasang

Sumber semua file: `local-debug/stability-test-20260830/`.
Backup file di SD terlebih dahulu dan tutup game sebelum menggantinya.

| Tahap | File | Tujuan pada SD |
| --- | --- | --- |
| 1: runtime | `pes21_nx.nro` | `switch/pes21_nx/pes21_nx.nro` |
| 2: scoreboard | `patch.305030001.jp.nyan2021.pesam.obb` | `switch/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb` |
| 3: rumput | `PesMobile-Android_ETC1_P.pak` | `switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak` |

Jangan salin `.elf`, `.nacp`, atau seluruh folder build. Tidak perlu mengganti
`libUE4.so`, main PAK, `Download/`, respons offline, atau `SaveData/`.
OBB scoreboard tetap **1,391,120,384 byte**, sama dengan OBB all-team sebelumnya.
Semua data roster/stat/foto tetap identik; hanya atlas scoreboard yang berubah.
Pastikan tidak mencampur salinan patch visual eksperimen lain di folder Paks.

### Urutan tes

1. Pasang **NRO saja** dahulu. Cek title screen/Press A dan helper muncul.
   Mainkan Barca–Madrid, lalu Inter–Napoli, lalu satu pertandingan lagi tanpa
   menutup aplikasi. Cek frame pacing saat gameplay, replay, dan kembali menu.
   Tahan Y saat defense: cek apakah rekan membantu menekan; lepas Y, pause,
   dan pergantian possession harus mengakhiri bantuan itu. Pastikan Y offense
   tetap menendang dan kontrol lain tidak berubah.
2. Bila runtime lolos, pasang OBB scoreboard. Cek waktu/skor, nama tim, tambahan
   waktu, update gol, half-time, dan full-time. Foto/stat pemain harus tetap sama.
3. Pasang PAK rumput terakhir. Cek garis tengah hanya satu, posisi garis gawang,
   replay dekat/jauh, stadion siang/malam, dan transisi LOD. Detail tekstur boleh
   lebih halus, tetapi garis tidak boleh hilang atau bergeser.

Jika crash berulang, simpan crash report Atmosphere terbaru dan catat tahap,
tim, match keberapa, serta apakah terjadi ketika replay/transisi. Jangan
menganggap memory retention sebagai satu-satunya penyebab sebelum tes ini.

### Rollback

- NRO dan PAK sebelumnya tersedia di subfolder `rollback/` kandidat.
- OBB sebelumnya masih utuh di `dist/pes21_nx/`; hash ada di manifest kandidat.
- Ganti kembali file tahap yang menyebabkan regresi. Jangan hapus SaveData.

## Validasi yang sudah lulus

- Build/link NRO release devkitPro/libnx dari snapshot stable.
- Host test C dengan UBSan: partial unmap, overlapping/repeated unmap,
  zero-fill/file read, invalid fd, rollback gagal alokasi, overflow, dan
  400 lifecycle alokasi dari empat thread. Live backing kembali nol.
- Host test adapter FriendPress: held/expiry/release, gate defense/local,
  missing history, dan restorasi input setelah native call.
- Empat tes Python synthetic: LZSS roundtrip/truncation serta inline/separate
  mip payload dan offset bulk PES21/EF10. Tidak membutuhkan game assets.
- PAK dibuka kembali: 15 file, enam texture, 35 mip terdecode; header/metadata,
  alpha, dan blok garis dibandingkan dengan PAK **stock aktual**.
- Scoreboard: 25 region dicek, hanya empat pelat berubah; metadata scripts,
  layout, alpha, dan region lainnya identik.
- OBB: 421 member dt210 lainnya dan 23 member OBB lainnya byte-identical.
  Ukuran OBB tidak berubah, sehingga tidak menambah perubahan whitelist NRO.

Belum ada smoke test boot/gameplay lokal untuk kandidat ini; screenshot pengguna
kemudian mengonfirmasi paket visual tampil di gameplay (lihat baseline di atas).
Uji GUI lokal via skill
`computer-use` terhalang Node runtime yang terlalu lama untuk helper tersebut;
runtime sistem tidak diubah. Host test mmap bukan pengujian jalur kernel
`svcMapMemory` di Switch, dan host test FriendPress tidak mengeksekusi game asli.

## Reproduksi asset pipeline

Gunakan input game milik sendiri. Semua hasil ekstraksi/build tetap di
`local-debug/` yang di-ignore, jangan stage/publikasikan payload game.
Dependensi Python: `tools/visual-patch-requirements.txt`; encoder Android SDK
`etc1tool`, `retoc` dan `repak` disediakan lokal oleh pengembang.

```powershell
python tools/extract_efootball10_visuals.py
python tools/build_efootball10_visual_patch.py
repak pack --version V8A --compression Zlib local-debug/stability-visuals/built/pitch-stage local-debug/stability-test-20260830/PesMobile-Android_ETC1_P.pak
python tools/prepare_visual_test_bundle.py
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/validate_efootball10_visual_patch.py --stock local-debug/stability-visuals/verified-stock
```

`--pes21` pada builder harus menunjuk hasil ekstraksi **stock** dengan struktur
`PesMobile/Content/...`, bukan hasil patch lama. `--score-base` adalah member
game2dPes.bin native yang sudah didekompresi WESYS. Validator `--stock` menunjuk
hasil ekstraksi pembanding dari main PAK aktual. Pembuat OBB menolak menimpa
kandidat yang sudah ada; gunakan `--output` baru bila mengulang.
