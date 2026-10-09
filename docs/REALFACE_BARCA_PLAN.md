# REALFACE BARCA — rencana konversi Football Life 26

Tanggal: 9 Oktober 2026  
Status: Yamal V19C dan Raphinha V1 diterima pengguna di Switch pada 9 Oktober
2026 dan menjadi referensi realface berikutnya. Hash serta batas penerimaannya
dicatat di [audit konversi](PES21_PC_FACE_TRANSFER_AUDIT.md). Batch seluruh
Barcelona dan otomatisasi dari sumber mentah belum selesai. Runtime lokal
aktif belum diganti.

Targetnya adalah realface untuk seluruh skuad Barcelona dalam dataset game yang
dipakai, dengan sambungan wajah–leher–baju yang rapi dan warna kulit yang selaras.
Metode berikutnya memakai model PES21 Mobile sebagai acuan sejak awal: muat
referensi native, tempatkan model Football Life 26 di atasnya, sesuaikan ukuran
dan sambungannya, lalu keluarkan geometri referensi dari hasil ekspor.

Pengerjaan dimulai dari Yamal untuk membuktikan metode, dilanjutkan kelompok
kecil pemain Barcelona dengan karakteristik berbeda, kemudian seluruh skuad.
Setelan yang berhasil menjadi profil yang dapat dijalankan ulang oleh skrip.

## Progres eksperimen Yamal

- V19C memuat referensi face native dan tubuh lengkap `001a01p` sebelum model
  FL26 yang sudah dikonversi pada V18. Fitting dibatasi ke leher/dada bawah,
  termasuk interpolasi bobot tulang dari permukaan native. Geometri referensi
  dikeluarkan dari FBX dan PAK hasilnya.
- Mata kiri pada gambar diperbaiki berdasarkan bukaan kelopak dalam sumbu X
  **dan Z**. Koreksi arah global (A) membuatnya lebih ke tengah; koreksi X saja
  (B) masih terlihat menunduk. C menaikkan pupil kiri sekitar 0,134 cm dan
  menggesernya ke luar sekitar 0,076 cm dari V18. Mata kanan dikunci.
- `skin4` Yamal diterapkan kembali ke dt200 build `e861c583ec78e9ae` setelah
  pemeriksaan identitas dan hash row. Ini bukan dt200 lama dari checkpoint.
- Cook, rig, ekspor ulang, integritas PAK dan perbandingan isi CPK lolos.
  Preview Blender belum membuktikan hasil animasi, kerah atau warna di Switch.
  Model body `001a01p` adalah referensi tubuh lengkap yang tersedia; pemilihan
  varian kerah persis yang dipakai kit Barcelona saat runtime belum dipastikan.
- Pemain yang tidak mempunyai sumber FL26 boleh dilewati sesuai arahan pengguna.
  Catat `skipped_missing_source`, tanpa mengganti atau menggandakan identitasnya.

Skrip [`realface_pipeline.py`](../tools/realface_pipeline.py) versi awal sudah
menjalankan fitting referensi, ekspor FBX, pemeriksaan pose sintetis, hash cache,
resume, pemeriksaan identitas dan laporan batch dari **input yang telah disiapkan**.
Contoh manifest lokal Yamal berada di
`local-debug/realface-yamal-v19/manifest-yamal.json` (input opsional, diabaikan Git).

```powershell
python tools/realface_pipeline.py plan --manifest <manifest-lokal>
python tools/realface_pipeline.py run --manifest <manifest-lokal> --player 162114 --resume
```

Manifest memuat `registry`, `blender`, `work_dir`, dan daftar profil `players`.
Setiap profil berisi BaseId, native ID, fingerprint, `source_status`, path
`face_fbx`, `native_face`, `native_body`, `native_rig`, `cooked_rig`, material skin,
serta parameter fitting/mata. Buffer glTF ikut masuk kunci cache. Jangan memakai
angka fitting Yamal sebagai nilai bawaan semua pemain. Resep Yamal memakai
z 138–159 cm, fitting penuh sampai 155 cm, batas gerak 1 cm, jarak referensi
maksimum 3 cm, blend bobot 1, dan clearance baju 0,06 cm. Referensi mata adalah
`negative_x`, yaitu kanan pada preview depan.

Pengendali ini belum mengekstrak sumber mentah FL26, memilih donor/kit,
menjalankan cook/package satu perintah, atau menyatakan penerimaan perangkat.
Import UE tersedia sebagai [`ue_import_realface.py`](../tools/ue_import_realface.py)
dalam project sementara yang sudah mempunyai dependency material/skeleton.
Kandidat dibuat dengan tahapan cook/package lokal yang diverifikasi.

## Progres eksperimen Raphinha

- Pemain kedua dipilih langsung oleh pengguna. BaseId/native ID/face owner
  `110644`, fingerprint `a127e8032d5e1bdff42a`; nama, kebangsaan dan posisi
  diperiksa pada database runtime saat ini serta database FL26. Sumber face
  tersedia di input lokal FL26. Skin native `2` dipertahankan.
- Face dan rambut FL26 memakai kompensasi bind terhadap skeleton native.
  Leher mengikuti face native milik Raphinha dan body referensi `001a01p`.
  Batas fitting khusus profil ini 1,15 cm; perpindahan terukur maksimum
  1,13248 cm. Model referensi tidak ikut diekspor sebagai mesh tambahan.
- Sesuai koreksi pengguna, mata generik PC diganti geometri mata asli PES21
  milik Raphinha: 102 vertex, 80 segitiga, UV dan tekstur native. Seleksi area
  native harus eksplisit dan cocok dengan jumlah yang diaudit. Tidak ada bola
  mata generik atau salinan iris donor dalam kandidat ini.
- Pengguna menerima mata kiri pada preview depan (`positive_x`) tetapi mata
  kanan terlihat terlalu ke luar. Profil V1 memutar hanya mata kanan
  (`negative_x`) sebesar -5 derajat pada sumbu Z native, menuju hidung. Pivot
  diambil dari globe native; bentuk, skala, UV dan posisi vertikal tetap.
  Seluruh 51 vertex mata kiri dikunci. Ini koreksi profil Raphinha, bukan default
  untuk pemain lain atau pengubahan ulang mata Yamal V19C.
- [`blender_use_native_eyes.py`](../tools/blender_use_native_eyes.py) menjalankan
  transfer dan koreksi yaw opsional, lalu memeriksa round-trip FBX. Parameter
  `gaze` menyebut `side`, `yaw_degrees`, `native_pivot_cm` dan
  `expected_vertices`; yaw di luar 12 derajat ditolak. UV mata native tidak
  memakai landmark tengah atlas (.5, .5), sehingga jangan menerapkan fitting
  pupil generik Yamal langsung pada atlas ini.
- [`ue_prepare_realface.py`](../tools/ue_prepare_realface.py) menyiapkan import
  baru dalam proyek UE sementara dengan kebijakan material eksplisit. PAK
  hanya membawa 15 asset files pemain dan satu marker; skeleton, body,
  material global, dan placeholder face material tidak ikut dibawa. Tekstur
  mata disalin dari native lewat rename nama paket beserta hash yang valid;
  payload dan hasil decode pixel tetap identik.
- Cook, rig 29 tulang, geometri/UV mata hasil cook, hash unpack PAK dan ZIP
  lolos. Kandidat gabungan ada di ignored
  `local-debug/realface-raphinha-v1/release/`. Yamal V19C dan pasangan
  dt200/manifest build `e861c583ec78e9ae` tetap byte-identical dengan paket
  sebelumnya. Tampilan, kerah, animasi dan performa Switch belum diterima.

Tahap transfer mata native dan persiapan UE sudah dapat diulang dengan profil
lokal; belum dirangkai menjadi satu perintah ekstraksi FL26 sampai packaging
seluruh skuad. Pipeline fitting/resume di atas tetap terbatas pada input yang
sudah disiapkan.

## Dasar yang sudah diperiksa

Rujukan utama: [audit transfer face](PES21_PC_FACE_TRANSFER_AUDIT.md).

| Temuan | Implikasi untuk eksperimen berikutnya |
| --- | --- |
| Checkpoint lokal Yamal V18 + pilihan body `skin4` telah diterima, dengan sedikit clipping dada yang masih ditoleransi | Jadikan pembanding dan rollback; pertahankan kemiripan wajah, mata, rambut, dan hasil warna yang sudah diterima |
| V16–V18 sudah memakai permukaan face native `133157` sebagai referensi, tetapi belum merupakan fitting terhadap tubuh dan kerah lengkap | Acuan berikutnya harus mencakup tubuh, leher, bentuk badan, serta baju yang benar-benar dipakai pemain |
| Mengecilkan seluruh leher dan menurunkan dada pernah membuka lubang atau sambungan yang buruk | Hindari koreksi global; gunakan daerah sambungan yang dibatasi dan perpindahan terukur |
| Jalur konversi memakai kontrak skeleton native 29 tulang serta kompensasi perbedaan bind pose | Model yang terlihat pas di Blender belum cukup; hasil setelah import/cook dan saat bergerak harus diperiksa |
| Warna tubuh berasal dari pilihan `skin1`–`skin6`, terpisah dari tekstur wajah | `skin4` adalah keputusan khusus Yamal, bukan preset seluruh Barcelona |
| Resep V18 masih berupa skrip eksperimen dengan path dan angka khusus Yamal | Resep tersebut perlu dipisahkan menjadi algoritme umum dan profil per pemain sebelum batch |

Snapshot selector lokal yang terakhir dipakai, build `e861c583ec78e9ae`, memuat
29 slot Barcelona (`team_id=108`). Registry publik yang diperiksa masih
menyebut build `1852ec648d2ebd75` dan 33 anggota Barcelona. Beberapa ID di
snapshot selector tidak ditemukan atau memiliki assignment berbeda dalam
registry tersebut. Ini belum membuktikan kesalahan roster; kedua snapshot
tidak boleh langsung digabung sebagai bukti identitas.

Model sumber Yamal, checkpoint V18, dan executable UE4.22 lokal masih tersedia.
Kelengkapan sumber wajah FL26 untuk seluruh skuad dan referensi tubuh/baju native
belum diaudit. Jumlah final target dikunci pada inventaris sebelum konversi.

## 1. Kunci roster, identitas, dan input

Ambil roster dari pasangan NRO/LooseCpk yang dipilih untuk pengujian. Cakup
semua pemain terdaftar, termasuk cadangan dan kiper. Jangan mengubah transfer
atau susunan tim untuk memudahkan konversi.

Buat manifest lokal per pemain yang mencatat:

- BaseId, fingerprint identitas, NativePES21Id, dan pemilik face yang berlaku;
- bukti kecocokan identitas pada dataset aktif dan sumber FL26;
- lokasi serta hash model/tekstur sumber, referensi native, dan profil fitting;
- tinggi/bentuk tubuh, pilihan skin, serta variasi kit yang perlu diuji;
- status sumber dan hasil: tersedia, identitas belum cocok, sumber tidak ada,
  perlu penyesuaian, siap diuji, atau diterima di perangkat.

Nama folder FL26 atau kesamaan nomor slot saja tidak menjadi bukti bahwa
pemainnya sama. Rekonsiliasi registry dengan dataset aktif harus selesai
sebelum menulis aset ke suatu ID. Pemain yang juga tampil di tim nasional
memakai satu identitas dan satu hasil face yang sama.

Semua pemain Barcelona masuk daftar target. Face FL26 yang tersedia dan cocok
menjadi calon pengganti, termasuk pemain yang sudah memiliki face native.
Face native tetap menjadi fallback sampai penggantinya lolos. Sumber yang
hilang atau ambigu dicatat sebagai pekerjaan tertunda, bukan dianggap sudah
berhasil hanya karena game masih dapat memakai fallback.

## 2. Bangun scene referensi native terlebih dahulu

Siapkan scene kerja dengan tiga kelompok terpisah:

| Kelompok | Isi | Peran saat ekspor |
| --- | --- | --- |
| Referensi native | Kepala/leher asli, tubuh, baju/kerah, skeleton dan parameter bentuk badan target | Geometrinya hanya untuk acuan dan pemeriksaan |
| Model FL26 | Wajah, mata, rambut, serta komponen mulut atau aksesori yang memang tersedia | Menjadi geometri kandidat |
| Hasil ekspor | Mesh kandidat dan armature yang sesuai kontrak native | Satu-satunya pilihan ekspor |

Gunakan ukuran badan dan posisi kerah pemain target. Jika pemain belum memiliki
realface native, acuan kepala generic atau donor dipilih secara eksplisit untuk
kebutuhan pemasangan; identitas dan aset wajah donor tidak diwariskan ke pemain.

Samakan satuan, sumbu, orientasi, dan rest/bind pose sebelum membandingkan
permukaan. Kepala native membantu menentukan posisi serta sambungan, sementara
bentuk wajah FL26 tetap menentukan kemiripan pemain. Align wajah, mata, rambut,
dan komponen terkait sebagai satu kelompok agar tidak saling bergeser.

Referensi native dikeluarkan dari daftar ekspor setelah pemeriksaan, tetapi
tetap disimpan dalam scene kerja untuk reproduksi. Armature/binding yang
dibutuhkan kandidat tetap ada. PAK akhir merujuk skeleton native runtime;
salinan skeleton atau material dasar dari proyek sementara tidak ikut dikirim.

## 3. Buktikan fitting pada Yamal

Mulai dari hasil V18 untuk mengisolasi perbaikan sambungan. Simpan perbandingan
depan, samping, belakang, serta sudut bawah dagu dengan tubuh dan kerah terlihat.

Urutan fitting yang diusulkan:

1. Periksa posisi kepala, garis mata, pivot leher, skala, dan batas bahu di ruang
   native. Hindari mengubah wajah agar menyerupai bentuk kepala donor.
2. Tetapkan daerah yang boleh berubah pada leher bawah dan tepi dada berdasarkan
   landmark/model target. Jangan memakai batas koordinat Yamal sebagai aturan
   global untuk semua pemain.
3. Sesuaikan daerah sambungan secara bertahap terhadap permukaan native yang
   relevan, dengan batas perpindahan dan transisi halus ke daerah yang dikunci.
   Hindari proyeksi ke sisi kerah yang salah atau menarik seluruh leher ke dalam.
4. Periksa ruang antara kulit dan baju, lubang di tenggorokan/leher belakang,
   serta sambungan antarbagian mesh. Pertahankan UV dan detail wajah; perbaiki
   normal hanya pada daerah yang membutuhkan transisi baru.
5. Verifikasi bobot tulang leher, kepala, dan bahu di kontrak native. Ubah bobot
   lokal hanya bila pengujian pose menunjukkan kebutuhan; bobot bagian wajah
   yang sudah benar tetap dipertahankan. Catat perubahan bobot dalam laporan.
6. Export, import ulang, cook, lalu bandingkan hasil akhirnya terhadap target di
   ruang native. Uji kepala menoleh/menunduk, berlari, dan selebrasi dengan bahu
   terangkat; pose diam saja tidak menentukan kelulusan.

Bagian source tidak dibuang hanya berdasarkan nomor mesh. Pada eksperimen lama,
bagian yang tampak seperti attachment ternyata juga mencakup kelopak/socket.
Klasifikasi harus berdasarkan fungsi geometri dan material. Konversi ini juga
belum menjamin ekspresi wajah native; gerak mata/mulut dinilai terpisah.

Jika fitting terbatas tetap gagal pada pose tertentu, evaluasi rekonstruksi
bagian sambungan leher sebagai eksperimen tersendiri. Jangan membuatnya menjadi
operasi batch otomatis sebelum topology, UV, bobot, dan geraknya terbukti.

## 4. Selaraskan warna kulit dan respons material

Pisahkan masalah tekstur/material wajah dari pengaruh pencahayaan stadion.
Bandingkan wajah–leher–tangan pada build, kamera, kit, dan pengaturan yang sama.
Gunakan pencahayaan siang sebagai pembanding, lalu uji Night + High yang menjadi
pengaturan pengguna dan preset lain yang didukung.

Urutan koreksi:

1. Periksa assignment material skin, mata, rambut, normal, serta interpretasi
   tekstur. Pertahankan jalur material native yang telah bekerja; shader
   diffuse-only pada eksperimen V13 pernah menghasilkan warna yang buruk.
2. Pilih varian body `skin1`–`skin6` yang paling sesuai dengan warna kulit pemain
   pada face sumber. Buat pilihan per pemain; Yamal `skin4` menjadi pembanding.
3. Jika masih ada batas warna, uji koreksi lokal pada tekstur skin di daerah
   sambungan dengan mask dan transisi halus. Hindari perubahan pada mata,
   bibir, rambut, atau detail khas pemain. Ukur dalam ruang warna yang konsisten.
4. Bandingkan hasil pada siang dan malam. Koreksi yang hanya menutupi cast hijau
   global pada satu kondisi tidak dijadikan profil warna pemain.

Simpan pilihan skin dan koreksi warna sebagai profil yang dapat direproduksi.
Gunakan mekanisme pemeriksaan identitas dan hash pada
[`patch_player_skin.py`](../tools/patch_player_skin.py). Tambahkan penerapan
profil ke alur pembuatan dataset agar tidak hilang saat data dibuat ulang.

Checkpoint V18 membawa dt200/manifest lama. Jangan menyalin paket itu di atas
data terbaru. Terapkan kembali hanya override pemain yang diperlukan pada
baseline aktif yang sudah diverifikasi, lalu bangun manifest/pasangan runtime
yang konsisten. Perubahan pemain lain harus tetap utuh.

## 5. Susun otomatisasi setelah metode Yamal lolos

Manfaatkan alat yang sudah ada:

- [`export_pes_fmdl_gltf.py`](../tools/export_pes_fmdl_gltf.py): pembacaan sumber,
  konversi koordinat, dan pemetaan rig;
- [`blender_export_ue_fbx.py`](../tools/blender_export_ue_fbx.py): transformasi,
  kompensasi bind, serta ekspor FBX;
- [`patch_player_skin.py`](../tools/patch_player_skin.py): override skin yang
  dibatasi identitas dan isi record.

Rencanakan satu pengendali `tools/realface_pipeline.py` untuk inventaris,
persiapan referensi, fitting, tekstur, ekspor, cook, validasi, dan packaging.
Perintah lengkap di bawah tetap rancangan. Implementasi awal di atas baru
mencakup tahap fitting dan validasi input yang sudah disiapkan.

```text
python tools/realface_pipeline.py plan --team-id 108 --config <config-lokal>
python tools/realface_pipeline.py run --manifest <manifest-barca> --player 162114 --resume
python tools/realface_pipeline.py run --manifest <manifest-barca> --resume
python tools/realface_pipeline.py package --manifest <manifest-barca> --require-accepted
```

Setelah profil awal disetujui, perintah `run --resume` menjadi cara mengulang
proses. Pipeline membutuhkan perilaku berikut:

- Cache berdasarkan hash sumber, referensi native, profil, dan versi alat.
  Hasil lama hanya dilewati jika output dan hash masih cocok.
- Tahap yang gagal dapat dilanjutkan; kegagalan satu pemain tidak membuang hasil
  pemain lain. Jangan meneruskan output gagal ke paket siap pakai.
- Parameter umum dipisahkan dari override per pemain, termasuk mata, mask
  sambungan, toleransi geometri, material rambut, dan pilihan skin.
- Simpan preview sebelum/sesudah, overlay native, metrik perubahan, log tahap,
  dan alasan kegagalan. Kasus di luar toleransi masuk daftar peninjauan.
- Bedakan lolos pemeriksaan otomatis dari diterima di Switch. Catatan penerimaan
  terikat ke hash kandidat dan baseline pengujian; output yang berubah perlu
  dinilai lagi.
- Registry, profil skin, nama paket, dan pemilik face harus konsisten. Regenerasi
  dataset tidak boleh diam-diam menghapus pilihan skin atau memasang face donor.

Skrip dapat mengotomatisasi resep yang telah terbukti. Sumber dengan topology,
rambut, mata, atau proporsi yang berbeda tetap mungkin membutuhkan penyesuaian
profil sekali sebelum pengulangan dapat berjalan tanpa edit manual.

## 6. Tahapan pelaksanaan dan syarat lanjut

| Tahap | Hasil yang harus tersedia sebelum lanjut |
| --- | --- |
| Inventaris Barcelona | Roster dan pasangan runtime terkunci; mapping identitas serta ketersediaan sumber dilaporkan untuk semua slot |
| Yamal dengan referensi lengkap | Sambungan membaik terhadap V18 tanpa merusak wajah/mata/rambut; warna dan gerak lolos pemeriksaan perangkat |
| Kelompok kecil Barcelona | Lima pemain termasuk Yamal, dipilih setelah inventaris agar mewakili ukuran badan, leher, rambut, warna kulit, dan kit kiper yang berbeda |
| Otomatisasi | Kelompok kecil dapat dibuat ulang dengan profil dan resume; kegagalan, cache, serta validasi bekerja tanpa angka khusus Yamal tersembunyi |
| Seluruh skuad | Setiap pemain mempunyai hasil atau alasan tertunda yang jelas; batch diuji untuk loading, memori, frame time, dan ukuran paket |
| Kandidat paket Barcelona | Semua target yang dinyatakan selesai telah diterima; tersedia daftar isi/hash, cara memasang, dan rollback yang cocok dengan baseline |

Pemeriksaan otomatis mencakup hierarki/bind tulang, bobot valid dan ternormalisasi,
koordinat finite, UV/material yang benar, orientasi permukaan, drift di daerah
yang dikunci, serta komponen mata/rambut yang tidak hilang atau rangkap.
Round-trip dan pemeriksaan isi PAK memastikan tidak ada geometri referensi,
skeleton pengganti, atau perubahan material global yang tidak direncanakan.

Tambahkan tes bermakna untuk pemetaan identitas yang ambigu, batas fitting,
transformasi rig, hanya bit skin yang diizinkan berubah, resume/cache, dan
penolakan paket yang belum lolos. Gunakan fixture sintetis untuk tes publik;
tes yang membutuhkan aset lokal melaporkan input yang tidak tersedia.

Pemeriksaan visual memakai kit home/away dan kiper, close-up dari beberapa arah,
pose bergerak, pergantian pemain, replay, serta pemain yang tampil di klub dan
tim nasional. Semua varian kit/LOD yang benar-benar dipanggil runtime perlu
tercakup. Ukur beban rambut/geometri satu tim di Switch sebelum menetapkan
batas batch; keberhasilan satu face belum membuktikan performa satu skuad.

## Penyimpanan dan hasil akhir yang direncanakan

Commit hanya kode, tes, profil buatan proyek, dan dokumentasi. Model/tekstur
sumber, ekstraksi, scene Blender, FBX, hasil cook, CPK, PAK, serta laporan yang
memuat data mentah game tetap lokal dan diabaikan Git.

Gunakan sumber lokal yang sudah ada tanpa menggandakan OBB. Intermediate dan
preview berada di staging sementara; hapus yang tidak lagi diperlukan setelah
validasi. Pertahankan temuan di dokumentasi dan resep di source, bukan bergantung
pada folder eksperimen. Promosikan hanya hasil tervalidasi ke runtime aktif dan
ikuti batas maksimal dua checkpoint runtime lengkap.

Hasil yang dituju adalah satu paket realface Barcelona yang dapat diuji dan
di-rollback, laporan cakupan seluruh skuad, serta pipeline yang dapat dipakai
ulang dengan mengganti manifest/profil tim. Kandidat Yamal adalah langkah awal;
paket seluruh skuad dan otomatisasi dari sumber mentah belum selesai.
