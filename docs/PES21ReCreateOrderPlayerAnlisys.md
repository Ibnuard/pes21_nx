# PES21 Re-Create / Re-Order Player Analysis

Analisis kelayakan **regenerate + reorder seluruh player ID PES21 mobile dari nol**,
supaya master data 1:1 dengan eFootball EF26 (mudah dimigrasi tiap update transfer).

Tanggal audit: 2026-09-14. Semua temuan di bawah **terverifikasi dari binary/asset
nyata**, bukan asumsi. Referensi bukti dicantumkan per poin.

---

## TL;DR

- **Commentary tidak putus saat reorder.** Nama pemain yang disebut komentator
  di-resolve dari **string nama**, bukan dari player ID atau kolom record.
  Reorder ID = zero impact. Tidak perlu tabel `baseId → callNameId`.
- **Real 3D face (wajah bintang) adalah SATU-SATUNYA risiko nyata.** Asset di-key
  **by player ID**. Reorder buta → "X pakai wajah Messi". Wajib di-handle.
- **Face-follow feasible** (Messi 26→14, wajah ikut). Runtime bangun path face dari ID
  (`RealFace/%d_face.uasset`), jadi cukup buat asset `14_*` + hapus `26_*`. Perlu rewrite
  internal path + kemungkinan repack Zen (retoc). Lihat **seksi 2b**.
- **Face params & portrait juga keyed by ID**, tapi ini data (bukan asset besar) dan
  sudah/gampang ikut dipindah.
- **EF26 feed hanya bawa data + portrait 2D, TIDAK ada 3D face.** Wajah 3D hanya dari base
  PES21 (2888) atau EF10 xapk. Lihat **seksi 5**.
- Kesimpulan: **reorder BOLEH**, asalkan setiap pemain membawa asset keyed-by-ID-nya
  (face params, star face 3D, portrait) ke ID baru. Join key lintas update = **BaseId**.

---

## Apa yang nyangkut di mana (peta terverifikasi)

| Data | Container | Di-key oleh | Ikut reorder otomatis? |
|---|---|---|---|
| Stats / ability / nama | `Player.bin` (312B/record) | isi record itu sendiri | Ya |
| **Commentary name-call** | `dt540 SA_ENG.acb` (483 R-code) | **string nama (runtime match)** | Ya (tidak terpengaruh ID) |
| Face params (kosmetik) | `PlayerAppearance.bin` (60B/record) | **player ID** | Tidak → copy row |
| **Real 3D face (star)** | UE4 IO Store (`<id>_face` / `SK_<id>_Face`) | **player ID** | Tidak → rename/pin |
| Portrait PNG | `dt241 common/player/<id>.png` | **player ID** | Tidak → sudah dihandle tool |

---

## 1. Commentary — TIDAK terikat player ID

### Bukti
- **Runtime hanya loader**, tidak ada mapping per-player.
  `source/ue4_hooks.c` (`pes_attach_commentary_sound_cpk`, `pes_use_commentary_enabled`)
  cuma mount ACB/AWB namespace `cpk_snd` untuk bahasa English (dt510/dt530) lalu return 1.
- **Struct atribut player max 8-bit.** Disasm `tmpdb::PlayerBase::GetData/SetData`
  (`.codex-player-getdata.txt`): jump table 108 field (index 0..0x6b), tiap field
  bit-extract dari struct in-memory 44-byte, lebar field maksimum `0xff` (8-bit).
  483 name-call code (`R0001..R9999`) butuh >8-bit → **tidak muat sebagai atribut**.
- **Scan on-disk record offset 44–250**: satu-satunya kandidat kecil (off 66) ternyata
  cuma **16 nilai** (kategori legend: Ronaldo=Messi=Maradona=R.Carlos=8), **bukan** 483
  name-code. Bukan field commentary.
- **Bank suara = keyed by R-code, bukan player.**
  `dt540 sound/match/acb/announce/SA_ENG.acb` → **483 name-call recording** `R0001..R9999`,
  dipakai di 7 konteks cue: `SA_PP1` (1500), `SA_PP3` (655), `SA_TGG/TLU/TSU/V1/V2` (99 each).
- `dt520 sound/config/Announce/sa_config.bin` = daftar cue generik ber-section
  (contoh `SA_01`), bukan mapping pemain. Tidak mengandung nama/ID pemain.

### Konsekuensi
Game me-resolve "nama pemain diucapkan" dengan mencocokkan **nama** pemain ke salah satu
483 rekaman. Selama converter menulis nama benar (`Messi`, `Ronaldo`), commentary jalan
**di ID berapapun**. Pemain baru EF26 yang tak punya rekaman (mis. Lamine Yamal) memang
tidak disebut namanya — itu **batas rekaman Konami**, bukan akibat reorder.

**Aksi reorder: TIDAK ADA.** Commentary aman total.

---

## 2. Real 3D Face (wajah bintang) — RISIKO UTAMA, keyed by player ID

### Bukti
- **Base PES21**: `PesMobile/Content/Assets/character/RealFace/<id>_face.uasset`
  (+ `_hair`, `_face_tablet`, `_hair_parts_color_tablet`).
  **2888 real face**, range ID 38..143275.
  Cross-ref `Player.bin`: **95% (2767/2888) adalah player ID valid.** Ronaldo (4522) &
  Messi (7511) punya real face.
- **EF10/EF26 import** memakai skema berbeda (uppercase, IO Store pc1000):
  `SK_<id>_Face`, `MI_<id>_Head_FaceLegacy_HQ/MQ`, `T_<id>_Face_D/N/SRO`, `_Hair`.
  Contoh terbukti: `SK_162114_Face` = Lamine Yamal (EF10 id 162114), `SK_7511_*` = Messi.
- **dt240 (model cpk) TIDAK menyimpan star mesh** — hanya `player-dummy.png`.
  Semua real face ada di UE4 IO Store (`pc1000` / `pakchunk0`), **keyed player ID**.
- **Runtime bangun path face DARI player ID.** Format string di `libUE4.so`:
  `Content/Assets/character/RealFace/%d_face.uasset` (`%d` = player ID).
  Cek keberadaan face juga by ID: `mode::ModePlayerAppearance::IsExistRealFaceData(uint)`,
  `draw::load::IsExistRealFace(uint)`. Loader: `APlayerActor::LoadRealFace(const char*)`,
  `UEPlayerModel::SetRealFace(const char*)`.
- Face montage/skin/eyelid/forehead juga templated by id
  (`FaceMontage/.../skin%d/...`, `eyelid/%d/...`, `forehead/%d/...`).

### Konsekuensi (persis kekhawatiran awal)
Reorder ID dari nol → asset `7511_face` tetap nyangkut di angka 7511. Kalau slot 7511
diisi pemain lain hasil reorder, pemain itu **mewarisi wajah Messi**.

### Aksi (pilih salah satu)
1. **Pin star di ID aslinya** — kunci ~2888 pemilik real-face base di ID lama, hanya
   reorder long-tail. Pola sudah ada di repo: `tools/recover_player_identity_pack.py`
   memaku Ronaldo di ID `4522` (`assert allocation[16781738]==4522`).
   Termurah & anti-rusak, tapi ID star jadi tidak urut EF26.
2. **Face-follow: pindahkan asset face ke ID baru** (target: master 1:1 urut EF26).
   Lihat seksi **2b** — sekarang feasible karena path di-derive dari ID.

---

## 2b. Face-follow reorder (Messi 26 → 14, face ikut) — FEASIBLE

Skenario: Messi awalnya ID `26`, hasil reorder jadi `14`. Mau: ID 14 dapat wajah Messi,
slot 26 (kini pemain lain) dapat wajah generik.

### Kenapa bisa
Karena loader **mengonstruksi path dari ID** (`RealFace/%d_face.uasset`), bukan lookup
tabel. Game hanya: ambil ID roster → susun string `RealFace/14_face.uasset` → ada? pakai :
tidak? generik. Jadi cukup **buat asset bernama `14_*` berisi wajah Messi**, dan **hapus
`26_*`**.

### Langkah per pemain yang di-reorder
1. Duplikat asset-set Messi, rename **semua** komponen `26_* → 14_*`:
   `26_face`, `26_hair`, `26_face_tablet`, `26_hair_parts_color_tablet` (+ `.uexp/.ubulk`).
2. Rewrite **internal package path** di dalam `.uasset` dari
   `/Game/Assets/character/RealFace/26_face` → `.../14_face`
   (string ini tertanam di asset — bukan cuma nama file).
3. Slot lama `26`: hapus `26_face.*` → `IsExistRealFace(26)` jadi false → generik.

### Kenapa langkah 2 & repack WAJIB (bukan sekadar rename file)
Ini IO Store (Zen). Lookup chunk = **hash(package path)**, bukan nama file. Kalau rename
file `26→14` tapi internal path tetap `26_face`, hash tetap milik "26"; loader minta
"14_face" → hash beda → **face tidak ketemu** (jatuh generik, gagal tujuan). Maka:
- rename file, **dan**
- rewrite internal path string, **dan**
- **repack** supaya chunk-ID di-hash ulang untuk path baru.

Tooling tersedia: `local-debug/tools/retoc-v0.1.5/retoc.exe` (`to-zen`, `pack-raw`,
`to-legacy`, `unpack`). Konversi Zen↔Legacy + repack didukung. **Belum ada script jadi**
untuk rename+repack face; perlu dibangun.

### Yang BELUM diverifikasi (menentukan berat kerja)
Apakah base PES21 memuat face dari **loose file** `Content/Assets/.../%d_face.uasset`
langsung, atau **harus** via `.utoc`/`.ucas` (IO Store).
- Jika loose-file didukung → cukup rename file + rewrite internal path (tanpa hash), ringan.
- Jika wajib IO Store → butuh repack retoc `to-zen` (hash ulang), lebih berat.

Uji: taruh satu `14_face.uasset` hasil rename Messi sebagai loose file, jalankan, lihat
apakah muncul. Ini canary 1-pemain sebelum otomatisasi massal.

---

## 3. Face params (kosmetik) — keyed by player ID, mudah dipindah

### Bukti
- `common/etc/appearance/PlayerAppearance.bin`: **record 60 byte, kolom 0 = player ID**
  (100% match ke `Player.bin`, 23576 row). Ronaldo & Messi punya row.
- Header raw (bukan WESYS): `09 00 00 00 74 79 55 45`.
- **Tidak ada flag "pakai real face"** di record ini — penggunaan real-face murni
  ditentukan keberadaan asset by ID (bandingan have vs lack face: tidak ada field yang
  membedakan).
- Converter EF10 saat ini (`tools/convert_efootball10_players.py`) **tidak menyentuh**
  file ini → itu sebabnya surrogate memakai wajah generik donor.

### Aksi reorder
Copy seluruh row 60-byte ke ID baru (pindah utuh; layout kosmetik internal tak perlu
di-dekode field-per-field untuk migrasi).

---

## 4. Portrait PNG — keyed by player ID, sudah dihandle

### Bukti
- `dt241_mobile_all.cpk` → `common/player/<pes21_player_id>.png` (128×128).
- Sudah ada pipeline: `tools/extract_efootball10_portraits.py` +
  `tools/import_efootball10_portraits.py` (crop safe-frame 100px, fallback transparan).
- Batasan: TOC dt241 tidak bisa **menambah** member baru dengan aman → portrait hanya
  bisa mengganti slot ID yang sudah ada (lihat `EFOOTBALL10_PLAYER_CONVERSION.md`).

---

## 5. Sumber data & batas visual per sumber

Penting dibedakan: **feed data EF26** vs **game EF10 xapk** vs **base PES21**.

| Sumber | Stats/nama/tim | Portrait | 3D face |
|---|---|---|---|
| **EF26 feed** (`tools/PESDBTools`) | ya | URL only (download on-demand) | **TIDAK ADA** |
| **EF10 xapk** (`EFOOTBALL10.xapk`) | ya | ETC2 thumbnail | **ada** (`SK_<id>_Face`) |
| **Base PES21** | ya | dt241 PNG | **ada** (2888, `<id>_face`) |

### Bukti
- `tools/PESDBTools/ef26_fields.json`: 150 field, **nol** field face/model/head. Field
  bernama "Header/Heading/BulletHeader" = skill heading bola, bukan head model.
- Portrait EF26 diturunkan dari ID → URL pesmaster (`Variation2022/<id>_.png`),
  tidak disimpan sebagai field.

### Implikasi ke reorder
- **Update EF26 tidak pernah menambah/ganti 3D face.** Wajah 3D bersifat statis, hanya
  dari base PES21 atau EF10 xapk. Tiap update EF26 = refresh data + portrait 2D saja.
- Ini **menyederhanakan** reorder: karena 3D face bukan bagian arus update EF26, satu-
  satunya kewajiban = jaga 2888 face jangan salah-tempel (via pin **atau** face-follow).
- Pemain baru EF26 (mis. Yamal) yang tak punya face base = portrait 2D ada, **3D face
  generik** — kecuali face-nya diimport dari EF10 xapk. Batas keras.

---

## Rekomendasi eksekusi

Reorder aman bila pipeline membawa, per pemain, tuple:
`(newID, record312, appearanceRow60, faceAssetRef, portraitPNG)`.

Yang WAJIB ikut ke ID baru saat reorder (semua keyed-by-ID):
`record312` (di-tulis), `appearanceRow60` (copy row), `portraitPNG` (rename), dan
`faceAsset` 3D (pin **atau** face-follow). Commentary tidak masuk daftar — aman by nama.

Join key lintas update EF26 = **`BaseId`** (Messi=7511, stabil antar versi), **bukan**
`Id` kartu (mis. 52788637736279, berubah tiap kartu/versi).

### Dua jalur (pilih sesuai target)

**Jalur A — Pin star (termurah, ID star tidak urut EF26)**
1. Pin ~2888 pemilik base real-face di ID aslinya (face + commentary aman otomatis).
2. Reorder bebas long-tail.
3. Tiap update EF26: match by `BaseId` → tulis ulang stats/nama/appearance/portrait.

**Jalur B — Face-follow (target user: master 1:1 urut EF26)**
1. Reorder semua ID sesuai urutan EF26 (Messi 26 → 14, dst).
2. Untuk tiap pemain yang punya real-face: pindahkan asset `oldID_* → newID_*`
   (rename file + rewrite internal path + repack Zen; lihat **seksi 2b**).
3. Slot lama yang kini kosong dari face: hapus `oldID_face.*` → jatuh generik otomatis.
4. Tiap update EF26: match by `BaseId`, ID sudah 1:1 → tulis data/portrait langsung.

Jalur B butuh **tool rename+repack face** yang belum ada di repo. Sebelum otomatisasi
massal, jalankan **canary 1-pemain** (uji loose-file vs harus IO Store — lihat 2b).

### Langkah lanjutan yang disarankan
1. Script audit crossref **2888 base-face ID vs roster EF26 target** → daftar
   "punya real face" (perlu dipin/difollow) vs "slot generik bebas".
2. Canary face-follow 1 pemain (mis. Messi) untuk memastikan berat kerja Jalur B.

Itu menjadi cetak-biru reorder.

---

## Sumber bukti (file yang diperiksa)

- Runtime commentary: `source/ue4_hooks.c`, `source/main.c`, `source/jni_fake.c`
- Struct player: `.codex-player-getdata.txt` (disasm `PlayerBase::GetData/SetData`)
- Converter: `tools/convert_efootball10_players.py`, `tools/recover_player_identity_pack.py`
- Data bin: `.../old_dt200_mobile_all.cpk/common/etc/pesdb/Player.bin`,
  `.../appearance/PlayerAppearance.bin`
- Audio: `.../cmp_dt520_mobile_all.cpk/.../Announce/sa_config.bin`,
  `.../cmp_dt540_mobile_all.cpk/.../announce/SA_ENG.acb`
- Face asset: `.../pitch-audit-20260826/base-full/.../character/RealFace/`,
  `.../pad-assets/assets/pc1000_mobile_and.utoc`
- EF26 data tools: `tools/PESDBTools/` (pesdb_efootball.py, README/USAGE/LIVE_UPDATE_NOTES)
