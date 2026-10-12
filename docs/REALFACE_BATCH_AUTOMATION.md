# Barcelona: inventaris dan pemasangan mata otomatis

11 Oktober 2026. Kandidat lokal; belum diterima di Switch.

Untuk perluasan ke seluruh tim Liga Inggris/Spanyol dalam selector, gunakan
[factory liga v22](REALFACE_LEAGUE_AUTOMATION.md). Pipeline tersebut menambahkan
cache per pemain, material rambut berulang, satu PAK gabungan, dan daftar
status lengkap yang dapat dicari.

Roster dikunci pada selector dan dt200 build `e861c583ec78e9ae`, team 108,
29 pemain. Ini mencakup transfer dalam dataset tersebut. Registry publik
snapshot lama tidak dipakai sebagai pengganti bukti identitas runtime.

| Hasil inventaris | Jumlah |
| --- | ---: |
| Sumber FL26 cocok nama lengkap dan kebangsaan | 21 |
| Pilot Yamal V19C dan Raphinha V1 yang dipertahankan | 2 |
| Identitas sumber belum cocok | 5 |
| Identitas cocok, payload sumber tidak lengkap | 1 |

18 dari 21 kandidat baru melewati fitting, cook final, serta audit rig,
geometri/UV/bobot hasil cook. Balde membutuhkan
material rambut dengan dua atlas dan UV berulang; Olmo gagal pemeriksaan
geometri/normal sumber; eyelid guide Bardghji kolaps ke titik kecil, sehingga
tidak dapat dipakai untuk menentukan bukaan mata. Ketiganya ditahan dan
fallback runtime dipertahankan. Pemain tanpa sumber: Xavi Espart, Hamza,
Jordi, Brian, Jesse, serta Eder (payload tidak lengkap). Tidak ada face donor
yang dipasang hanya karena nomor pemainnya sama.

## Jalur yang dapat diulang

- [`inventory_team_realfaces.py`](../tools/inventory_team_realfaces.py)
  memeriksa urutan selector, pemilik BaseId/native ID, fingerprint, record
  native, prioritas CPK, nama sumber dan kebangsaan. Offset serta identitas
  arsip dicatat dalam manifest lokal.
- [`extract_team_realfaces.py`](../tools/extract_team_realfaces.py)
  membaca hanya anggota face yang terverifikasi. Parser FPK/FTEX merupakan
  dependency lokal. Input yang berubah tidak ditimpa diam-diam.
- [`realface_pipeline.py`](../tools/realface_pipeline.py) versi 2 merangkai
  pemasangan mata opsional, fitting leher, round-trip FBX, pose sintetis,
  hash input/output dan resume dari profil yang telah disiapkan.
- [`audit_realface_rig.py`](../tools/audit_realface_rig.py) dan
  [`validate_realface_cooked.py`](../tools/validate_realface_cooked.py)
  memeriksa rig embedded dan geometri/UV/bobot setelah cook. Satu pasangan
  posisi/UV/bobot harus cocok pada vertex yang sama. Jumlah segitiga dan
  cakupan geometri juga diperiksa, termasuk vertex yang terpecah saat impor.

```powershell
python tools/inventory_team_realfaces.py --config <config-lokal> --output <inventaris-lokal>
python tools/extract_team_realfaces.py --inventory <inventaris-lokal> --work <output-lokal> --parser-root <parser-lokal>
python tools/realface_pipeline.py run --manifest <manifest-lokal> --resume
```

Manifest pipeline memakai registry lokal yang dikunci dari inventaris aktif.
`eye_preparation` pada setiap profil memuat `eyelid_rim`, `replace_material`,
`eye_material`, `source_policy`, serta `own_native_face` atau landmark template
`template_pupil_uv`. Tahap ekspor sumber, pemilihan material, cook dan packaging
masih memerlukan resep eksplisit; perintah di atas bukan konversi mentah ke
PAK seluruh tim dalam satu perintah. Input/output proprietary tetap lokal.

## Perbaikan mata

Atlas mata PES21 bersifat radial: V menyatakan radius iris, U mengelilinginya.
Tengah kotak UV bukan titik pupil. Mengambil titik itu menyebabkan koreksi
arah palsu dan mata tampak juling. Landmark yang benar adalah pole 3D tempat
vertex seam pada V ekstrem bertemu.

[`blender_fit_eye_sockets.py`](../tools/blender_fit_eye_sockets.py) memasang
kedua globe dari eyelid guide FL26 milik pemain, kemudian memakai ray test
terhadap kulit untuk mengukur bukaan yang benar-benar terlihat. Pupil
dipusatkan dalam X dan Z untuk masing-masing mata; target tidak dicerminkan
secara membabi buta dan yaw Raphinha tidak disalin sebagai default. Ukuran,
kedalaman, translasi dan rotasi yang berlebihan ditolak. UV/topologi mata serta
geometri, UV, bobot dan normal wajah di luar mata diperiksa setelah ekspor.

Sepuluh kandidat memiliki geometri/atlas mata native milik pemain sendiri.
Delapan lainnya memakai geometri dan iris template FL26 yang dinyatakan
eksplisit. Warna iris template bukan klaim warna mata asli pemain. Tidak ada
tekstur iris pemain donor yang diwariskan. Yamal/Raphinha tidak diproses ulang.

Pada Pedri ditemukan enam corner dengan normal sumber nol akibat smoothing
pada permukaan yang terlipat.
Perbaikan dibatasi ke corner yang tidak mempunyai arah, menggunakan normal
polygon; normal valid, UV, vertex, topology dan bobot tidak diubah. Perubahan
itu dicatat dalam laporan. Sumber dengan terlalu banyak normal rusak ditolak.

## Susunan file dan material Eric García

Kepala utama Eric berada di `hair_high.fmdl`; `face_high.fmdl` berisi lapisan
basah, eyelid guide dan bagian rambut. Nama `fox_skin_mat` pada file face
ternyata memakai shader efek basah. Pemisahan berdasarkan nama file/material
saja memasang transparansi rambut ke kulit pada preview, dan mengekspor
lapisan efek sebagai kepala. Kandidat awal tersebut tidak layak dipasang.

Resep koreksi mengambil kulit dari file hair, rambut dari file face dan
mengecualikan lapisan basah. Mata native Eric dipasang ke bukaan kepala yang
benar, lalu fitting leher diulang pada kepala utama. Preview koreksi sudah
menampilkan kepala dan rambut utuh. Pemeriksaan serupa memindahkan material
rambut yang bernama skin pada Gordon ke bagian rambut, dan mengecualikan
effect berlabel skin pada Adeyemi. Keduanya menjalani fitting/cook ulang.

[`realface_material_policy.py`](../tools/realface_material_policy.py) membedakan
skin, hair, effect dan guide dari teknik shader serta texture role. Shader
rambut dengan dua atlas ditandai untuk kebijakan/bake eksplisit. Klasifikasi
tidak otomatis mengimplementasikan shader FL26 tersebut. Kandidat memakai
jalur material native dan tekstur diffuse/alpha yang dipilih; oral, eyelash,
wet overlay dan efek sumber lainnya bukan port shader lengkap.

## Batas validasi

FBX dan cook tidak membuktikan kerah aktual kit, skin tone tubuh, ekspresi,
animasi atau performa di perangkat. Pilihan skin runtime tidak diganti sebagai
preset seluruh tim. Acuan body `001a01p` dipakai untuk fitting, bukan bukti
bahwa semua kit memakai kerah yang sama.

Kandidat berikutnya menambahkan kebijakan palet tubuh per identitas untuk
20 wajah gabungan. Lihat [match review v16](MATCH_REVIEW_V16.md#realfacebody-palette-matching)
untuk pengukuran warna, validasi BaseId/fingerprint dan batas pengujiannya.

UE4.22 membuang influence <=1% saat impor dan mengkuantisasi bobot vertex
Android ke delapan bit. Pemeriksaan cook membandingkan terhadap aturan itu,
tetap memeriksa posisi bind, UV dan cakupan sumber. Reference skeleton/body
dan material global adalah dependency cook; tidak boleh ikut allowlist PAK.

Eksperimen, manifest, preview dan paket berada di ignored
`local-debug/barca-realface-batch-v1/`. Paket final harus membawa hasil koreksi
Eric dan Pedri, bukan cook awal keduanya. Integritas ZIP/PAK dan jumlah pemain
dicatat dalam laporan release lokal. Tidak ada perubahan NRO untuk batch ini.

44 tes fokus konversi wajah lolos. Suite repository yang lebih luas belum
hijau: 666 lolos, 14 gagal di luar tes konversi wajah, dan 51 dilewati.
Pemeriksaan public tree lolos. Hasil ini tidak menggantikan pengujian Switch.

## PAK gabungan v2

Atas permintaan pengguna, Barcelona v1, Yamal V19C dan Raphinha V1 digabung
menjadi satu PAK dengan nama `PesMobile-Barcelona-Faces-Android_ETC1_P.pak`.
Gabungan ini memuat 20 wajah: 18 kandidat batch dan dua pilot yang sudah
diterima. Sembilan pemain yang tertunda tetap belum disertakan.

Hash ketiga PAK sumber harus cocok dengan laporan v1. Pemeriksaan awal menolak
tabrakan nama/path, aset di luar RealFace, dan native ID yang bukan pemilik
dalam inventaris batch. Ada 320 file aset ditambah tiga marker sumber dan
satu marker gabungan. Seluruh payload sumber dipertahankan byte-for-byte;
mesh, material, tekstur dan referensi internal tidak dimodifikasi atau dicook
ulang. Integritas PAK dan hash setiap entry hasil repack diperiksa lagi.

Output berada di ignored `local-debug/barca-realface-combined-v2/release/`.
Tutup game, ganti PAK Barcelona v1 dengan PAK gabungan, lalu keluarkan PAK
Yamal/Raphinha terpisah dari `Paks`. Backup ketiga PAK lama berada di luar
folder `Paks`, sehingga tidak ikut dimount. PAK game utama, stadium, dan
weather tetap digunakan. Untuk rollback, kembalikan ketiga PAK lama.
Penggabungan belum diuji di Switch; runtime lokal aktif belum diganti.

Pada rambut Eric, cook membuang dua segitiga transfer yang seluruh corner-nya
berada dalam rentang kurang dari 0,00001 cm. Resep Eric mencatat tepat dua
pengecualian tersebut; validator menolak perubahan jumlahnya maupun hilangnya
segitiga yang memanjang. Jumlah segitiga sumber/cook dan pengecualian dilaporkan
terpisah. Pemeriksaan posisi, UV dan bobot tetap berlaku.
