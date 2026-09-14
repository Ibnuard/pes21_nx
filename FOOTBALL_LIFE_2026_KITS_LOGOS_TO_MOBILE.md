# Tutorial mengambil kits dan logo Football Life 2026 ke PES21 Mobile/Switch

Panduan ini menjelaskan alur yang sudah dipakai di repository ini untuk mengambil
kit dan crest dari **SP Football Life 2026 (PES21 PC)**, mengubahnya ke format
PES21 Mobile, lalu memasukkannya ke OBB Switch. Contoh path menganggap Football
Life terpasang di `D:/Games/SP Football Life 2026` dan semua perintah dijalankan
dari root `public_pesnx`.

Alur ini hanya memindahkan identitas visual tim. Jangan mengganti seluruh
`Team.bin`, roster, tactics, `Player.bin`, portrait, atau face dengan tabel PC.
Gunakan OBB yang sedang menjadi basis proyek agar perubahan gameplay dan roster
yang sudah ada tetap ikut.

## 1. Peta aset PC dan Mobile

| Kebutuhan | Sumber Football Life 2026 | Tujuan PES21 Mobile/Switch |
|---|---|---|
| Descriptor kit | `common/character0/model/character/uniform/team/<id>/<id>_DEF_<kind>_realUni.bin` | `dt200_mobile_all.cpk/common/etc/uniform/team/<id>/...` |
| Texture badan kit | `Asset/model/character/uniform/texture/#windx11/<name>.ftex` | `dt120_mobile_all.cpk/Models/character/Uniform16/D/<name>.png` |
| Nomor/nama pemain | FTEX yang direferensikan descriptor | `dt120_mobile_all.cpk/Models/character/Uniform16/Font/<name>.png` |
| Flag real kit | byte offset 84 pada record tim | `dt200_mobile_all.cpk/common/etc/pesdb/Team.bin` |
| Crest native | `common/render/symbol/flag/e_<id>_*.png` | seluruh varian tim tersebut di `dt240_mobile_all.cpk` |
| Crest custom selector | crest Football Life yang sama | catalog dan `data/badge_atlas.bin` di NRO |

`dt120` menyimpan texture kit, `dt200` menyimpan descriptor dan database tim,
sedangkan `dt240` menyimpan crest untuk layar native seperti prematch, pause,
dan goal. Custom Team Select/Game Plan memakai badge atlas di NRO, sehingga logo
harus diterapkan ke **dt240 dan badge atlas**.

## 2. Siapkan input

Pastikan file berikut tersedia:

```text
D:/Games/SP Football Life 2026/Data/dt34_g4.cpk
D:/Games/SP Football Life 2026/download/data_s2526a.cpk
D:/Games/SP Football Life 2026/download/data_s2526b.cpk
D:/Games/SP Football Life 2026/download/data_s2526c.cpk
dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb
dist/pes21_nx/pes21_nx.nro
```

Urutan sumber kit adalah `dt34`, season `a`, `b`, lalu `c`. Jika member yang
sama ada di beberapa arsip, sumber terakhir menang. Tool mencatat archive,
member, ukuran, dan SHA-256 pemenangnya di `asset-report.json`.

Python memerlukan Pillow:

```powershell
python -c "from PIL import Image; print(Image.__version__)"
```

Pilih OBB/NRO basis yang memang sudah lolos pengujian di perangkat. Catat hash
sebelum membuat kandidat baru:

```powershell
Get-FileHash dist/pes21_nx/pes21_nx.nro -Algorithm SHA256
Get-FileHash dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb -Algorithm SHA256
```

Selalu gunakan folder output baru di `local-debug`. Tool produksi menolak
menimpa output lama agar kandidat yang sudah dites tidak berubah tanpa sengaja.

## 3. Buat manifest tim

Manifest menentukan tim yang diproses dan menjadi pengaman agar ID tim PC tidak
diterapkan ke slot Mobile yang salah. Contoh yang sudah ada:

- `data/eng_spa_license_overrides.json`
- `data/serie_a_license_overrides.json`
- `data/national_team_kit_overrides.json`

Struktur minimum yang dipakai converter:

```json
{
  "schema_version": 1,
  "scope": "nama_paket",
  "leagues": [
    {
      "key": "nama_liga",
      "label": "NAMA LIGA",
      "teams": [
        {
          "team_id": 120,
          "order": 1,
          "official_name": "Juventus FC",
          "short_code": "JUV",
          "catalog_integration": "existing",
          "team_bin_policy": "patch_existing"
        }
      ]
    }
  ]
}
```

Gunakan `team_id` fisik yang benar-benar tersedia pada `Team.bin` Mobile. ID
yang hanya ada di Football Life tidak boleh ditempelkan ke slot tim lain. Untuk
kasus seperti Como 1907 atau Sunderland yang belum mempunyai slot Mobile,
tandai `catalog_integration` dan `team_bin_policy` sebagai pending sampai team,
roster, tactics, crest, dan uniform ditambahkan sebagai satu paket.

Untuk semua tim nasional yang sudah tampil di selector, manifest dapat dibuat
ulang dari catalog:

```powershell
python tools/generate_national_team_kit_manifest.py
python tools/generate_national_team_kit_manifest.py --check
```

## 4. Audit nama, ID, descriptor, texture, dan crest

Jika paket juga mengubah nama resmi tim, jalankan tahap audit terlebih dahulu.
`Team.bin` dan `CompetitionEntry.bin` Football Life harus diekstrak dari database
PC yang sama dengan CPK kit. Contoh:

```powershell
python tools/build_eng_spa_license_pack.py `
  --manifest data/serie_a_license_overrides.json `
  --football-life-root "D:/Games/SP Football Life 2026" `
  --football-life-team local-debug/licensing-audit/football-life-Team.bin `
  --football-life-competition-entry local-debug/licensing-audit/football-life-CompetitionEntry.bin `
  --pes21-team local-debug/mobile-base/Team.bin `
  --output-dir local-debug/serie-a-license-audit
```

Hasil pentingnya:

```text
Team.bin
selector-name-overrides.json
kit-source-manifest.json
validation-report.json
```

Periksa `validation-report.json` sebelum lanjut. Jumlah record `Team.bin`
Mobile harus tetap sama dan byte di luar field nama, short code, serta flag kit
tim target harus tetap identik.

Untuk hanya mengambil crest dan menghubungkannya ke custom selector:

```powershell
python tools/integrate_club_licenses.py `
  --catalog data/exhibition_team_catalog.json `
  --names local-debug/serie-a-license-audit/selector-name-overrides.json `
  --crest-cpk "D:/Games/SP Football Life 2026/Data/dt34_g4.cpk" `
  --crest-cpk "D:/Games/SP Football Life 2026/download/data_s2526a.cpk" `
  --crest-cpk "D:/Games/SP Football Life 2026/download/data_s2526b.cpk" `
  --crest-cpk "D:/Games/SP Football Life 2026/download/data_s2526c.cpk" `
  --output local-debug/serie-a-identity
```

Argument `--crest-cpk` diberikan dari arsip paling lama ke terbaru. Tool mencari
varian `r_ll`, `r_l`, `r`, lalu `r_b`, memverifikasi PNG, dan menulis provenance
ke `report.json`.

## 5. Konversi kit PC menjadi texture Mobile

Jangan memasukkan FTEX PC langsung ke CPK Mobile. Converter melakukan perubahan
yang sudah diuji berikut:

- body FTEX 1024×1024 atau 2048×2048 menjadi atlas `Uniform16` 256×384;
- resize anisotropic tanpa crop dan tanpa mengubah susunan bagian jersey;
- output body berupa indexed PNG 256 warna tanpa dithering;
- texture nomor/nama dengan rasio 8:1 menjadi RGBA 320×40;
- descriptor PC 120-byte dipertahankan parameternya, lalu nama referensi texture
  dinormalisasi menjadi nama unik Mobile;
- descriptor native yang sudah bekerja dipertahankan;
- hanya flag real-kit pada offset 84 milik tim target yang diubah menjadi 15.

Contoh membangun Serie A di atas basis pilihan:

```powershell
python tools/build_eng_spa_mobile_kits.py `
  --base-obb dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb `
  --base-nro dist/pes21_nx/pes21_nx.nro `
  --license-manifest data/serie_a_license_overrides.json `
  --preserve-teams "" `
  --patched-team local-debug/serie-a-license-audit/Team.bin `
  --identity-overrides local-debug/serie-a-identity/identity-overrides.json `
  --output local-debug/serie-a-mobile-candidate
```

Contoh seluruh tim nasional:

```powershell
python tools/build_eng_spa_mobile_kits.py `
  --base-obb dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb `
  --base-nro dist/pes21_nx/pes21_nx.nro `
  --license-manifest data/national_team_kit_overrides.json `
  --preserve-teams "" `
  --output local-debug/national-mobile-candidate
```

Untuk liga atau kelompok tim baru, buat manifest dengan struktur yang sama dan
berikan melalui `--license-manifest`. Converter mengambil `p1`, `p2`, dan `g1`.
Jika hanya ingin memeriksa hasil PNG dan descriptor tanpa membuat CPK/OBB,
tambahkan `--assets-only`.

Output conversion berada di:

```text
local-debug/<candidate>/converted/<team_id>/p1-body.png
local-debug/<candidate>/converted/<team_id>/p1-back.png
local-debug/<candidate>/converted/<team_id>/p1-realUni.bin
local-debug/<candidate>/converted/<team_id>/p2-...
local-debug/<candidate>/converted/<team_id>/g1-...
```

Buka beberapa hasil home, away, dan goalkeeper sebelum packaging. Warna,
transparency, susunan bagian jersey, nomor, serta font harus masuk akal.

## 6. Terapkan logo ke dua jalur render

### Crest native di OBB

`build_eng_spa_mobile_kits.py --identity-overrides ...` mengganti seluruh member
crest yang sudah ada untuk ID tim target di `dt240`. Ukuran setiap output mengikuti
template member native. Saat sebuah tim baru diaktifkan sebagai real kit, tool
juga membuat alias `_r` dari crest `_f` bila loader membutuhkannya.

Jangan hanya mengganti satu file crest. Sebuah tim dapat mempunyai varian `_f`,
`_r`, `_l`, `_s`, `_b`, atau `_w` yang dipakai layar berbeda.

### Crest custom selector dan Game Plan di NRO

Promosikan catalog hasil integrasi dan buat ulang atlas:

```powershell
Copy-Item local-debug/serie-a-identity/exhibition_team_catalog.json data/exhibition_team_catalog.json
Copy-Item local-debug/serie-a-identity/exhibition_teams_generated.inc source/exhibition_teams_generated.inc

python scripts/generate_badge_atlas.py `
  --catalog data/exhibition_team_catalog.json `
  --symbol-root local-debug/cpk-emblem-check/common/render/symbol `
  --output source/badge_atlas.h `
  --binary-output data/badge_atlas.bin
```

Catalog hasil integrasi menunjuk langsung ke crest yang ditaruh di repository.
`symbol-root` tetap diperlukan untuk tim dan kategori lain yang tidak diubah.

Jika hanya menguji kandidat dan belum ingin mengubah generated files utama,
arahkan `--output` dan `--binary-output` ke folder `local-debug` terlebih dahulu.

## 7. Packaging CPK dan OBB

Batch converter mengerjakan tahap ini otomatis:

1. ekstrak `dt120`, `dt200`, dan `dt240` dari OBB basis;
2. ganti member yang sudah ada dan tambahkan member yang belum ada;
3. pertahankan urutan dan ID TOC existing;
4. tambahkan member baru di akhir dan set `Sorted=0`;
5. validasi semua payload yang tidak ditargetkan tetap byte-identik;
6. patch slot outer OBB jika kapasitas cukup, atau repack outer OBB bila perlu.

Untuk mengganti satu CPK yang ukurannya masih muat di slot OBB, tersedia:

```powershell
python tools/patch_cpk_slots.py `
  <base.obb> <output.obb> Expansion/dt120_mobile_all.cpk <dt120-baru.cpk>
```

Gunakan converter batch untuk pekerjaan normal karena laporan validasinya
mencakup semua perubahan. Jangan mengurutkan ulang seluruh TOC hanya supaya CPK
terlihat sorted; kandidat yang stabil mempertahankan urutan existing dan memakai
`Sorted=0` saat member baru ditambahkan.

## 8. Sesuaikan NRO dengan ukuran OBB

Jika ukuran OBB baru sama dengan basis, NRO lama dapat disalin oleh tool. Jika
ukurannya berubah, `validation-report.json` akan memberi status
`matching_size_allowance_build_required`.

Tambahkan ukuran aktual OBB kandidat ke kontrak eksplisit di `source/main.c`,
lalu bangun NRO production:

```powershell
(Get-Item local-debug/serie-a-mobile-candidate/patch.305030001.jp.nyan2021.pesam.obb).Length
.\build-wsl.ps1 -OutputDirectory local-debug/serie-a-mobile-candidate/production -Jobs 8
```

Salin NRO production tersebut ke folder kandidat dan selalu tes NRO/OBB sebagai
satu pasangan. Jangan memasangkan OBB baru dengan NRO yang belum menerima ukuran
OBB itu.

## 9. Validasi otomatis

Jalankan tes yang sesuai dengan paket:

```powershell
python -m pytest -q tests/test_barca_real_madrid_mobile_kit_canary.py
python -m pytest -q tests/test_eng_spa_mobile_kits.py
python -m pytest -q tests/test_serie_a_license.py
python -m pytest -q tests/test_national_team_kits.py
python -m pytest -q tests/test_runtime_obb_size_contract.py
```

Periksa pula `asset-report.json` dan `validation-report.json`. Minimal pastikan:

- setiap tim target mempunyai `p1`, `p2`, dan `g1`;
- setiap kit mempunyai body, back/font, dan descriptor;
- tidak ada konflik dua texture berbeda pada nama member Mobile yang sama;
- hanya tim target yang flag kit-nya berubah;
- CPK lain dalam OBB tetap byte-identik;
- crest native dan badge atlas berasal dari ID tim yang sama;
- OBB dan NRO mempunyai kontrak ukuran yang cocok.

## 10. Tes di Switch sebelum promosi

Tes berikut diperlukan karena validasi byte tidak dapat membuktikan seluruh
perilaku native loader:

1. boot sampai hub tanpa black screen;
2. buka Team Select dan periksa nama serta crest;
3. buka Kits dan periksa home, away, serta goalkeeper;
4. mulai pertandingan dan periksa jersey, nomor, serta nama pemain;
5. buka Game Plan dan pause untuk memeriksa kedua jalur crest;
6. cetak gol lalu tes celebration, skip, pause/resume, dan restart;
7. ulangi satu pertandingan memakai tim stable lama sebagai tes regresi.

Setelah seluruh alur lolos, baru salin pasangan kandidat ke `dist/pes21_nx` dan
catat ukuran serta SHA-256. Binary OBB/NRO bersifat lokal dan tetap diabaikan Git;
yang di-commit adalah manifest, tool, source size contract, tes, dan dokumentasi.

## Masalah yang sering muncul

| Gejala | Penyebab yang perlu diperiksa |
|---|---|
| Kit putih atau rusak | FTEX PC disalin langsung, ukuran atlas salah, atau descriptor menunjuk nama texture yang tidak ada |
| Nomor/nama jersey salah | shared font dari descriptor PC tidak dikonversi ke RGBA 320×40 atau referensinya ditebak |
| Crest benar di selector tetapi salah saat match | badge atlas sudah berubah, tetapi varian crest `dt240` belum diganti |
| Crest benar di pause tetapi salah di selector | `dt240` sudah berubah, tetapi catalog/include/atlas NRO belum dibangun ulang |
| Tim hilang atau roster berubah | seluruh `Team.bin` PC digunakan atau ID Football Life dipaksakan ke slot Mobile lain |
| Black screen setelah menambah member | TOC/ID/order CPK berubah, flag `Sorted` tidak cocok, atau slot outer OBB overflow |
| OBB ditolak saat boot | ukuran OBB belum ditambahkan ke kontrak `source/main.c` atau NRO/OBB tertukar |

Implementasi acuan utama berada di:

- `tools/build_eng_spa_mobile_kits.py`
- `tools/build_real_madrid_mobile_kit_canary.py`
- `tools/integrate_club_licenses.py`
- `scripts/generate_badge_atlas.py`
- `tools/package_native_club_license.py`
- `tools/patch_cpk_slots.py`
- `KITS_LOGOS_STABLE_MIGRATION.md`
