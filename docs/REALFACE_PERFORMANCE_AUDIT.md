# Audit biaya geometri real face

13 Oktober 2026. Audit baca-saja terhadap PAK real face liga v24 yang juga
mencakup Barcelona, dibandingkan dengan main PAK Mobile yang dipakai factory.
Pengguna melaporkan bahwa melepas patch real face menghilangkan masalah frame
pacing. Temuan di bawah menguatkan prioritas optimasi real face; pengukuran
GPU/CPU di Switch untuk memisahkan biaya skinning, draw submission, dan pixel
overdraw belum dilakukan.

## Cakupan dan bukti

- **897 pemain / 1.794 mesh** dari PAK gabungan, dibaca langsung dari paket
  hasil cook; bukan perkiraan jumlah polygon sumber FL26.
- **2.888 wajah dan 2.704 rambut** dari main PAK Mobile. Statistik kepala
  lengkap memakai 2.704 pasangan wajah+rambut. Sebanyak 184 wajah tanpa file
  rambut pasangannya tidak diasumsikan memiliki rambut berbiaya nol.
- Semua mesh yang diperiksa, baik native maupun patch, memiliki **satu LOD**
  dan rig berisi 29 tulang.
- Angka wajah mencakup mata/leher yang tersimpan di mesh itu. Rambut dapat
  mencakup kulit kepala. Body, seragam, sepatu, jumlah pass, dan jumlah pemain
  yang benar-benar terlihat pada suatu frame tidak masuk hitungan ini.
- Identitas patch berasal dari manifest rilis terverifikasi, menggunakan
  BaseId dan native storage ID. Kolom pembanding native slot dalam CSV hanya
  membandingkan biaya aset; slot yang sama tidak membuktikan identitas pemain.

Identitas input:

| Input | SHA-256 |
| --- | --- |
| Main Mobile PAK | `26a3969be6de9495e2b5f38866c4ae4698d304fae042e305cbba53fe61915036` |
| League faces v24 PAK | `6d62a14137904a1bcd3560d4ae36b1bce32bbb731bb2b7bbe22677d87f028315` |
| Mobile libUE4 | `a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187` |

## Jumlah segitiga

| Aset | Minimum | Median | P95 | Maksimum |
| --- | ---: | ---: | ---: | ---: |
| Wajah native, 2.888 mesh | 1.096 | 1.158 | 1.174 | 1.178 |
| Rambut native, 2.704 mesh | 2 | 200 | 482 | 776 |
| Kepala native, 2.704 pasangan | 1.132 | 1.358 | 1.647 | 1.924 |
| Wajah patch, 897 mesh | 4.496 | 5.156 | 7.792 | 27.256 |
| Rambut patch, 897 mesh | 1 | 4.490 | 14.070 | 79.010 |
| Kepala patch, 897 pasangan | 4.936 | 9.778 | 20.506,8 | 84.166 |

Median kepala patch **7,20 kali** median pasangan native. Semua 897 kepala
patch melampaui maksimum pasangan kepala native. Rambut bertanda satu
segitiga adalah placeholder transparan untuk sumber botak, bukan target
minimum kualitas rambut yang terlihat. P95 memakai interpolasi linear.

Median jumlah vertex kepala naik dari **1.085 menjadi 6.670**, sementara
median bagian mesh/material naik dari **2 menjadi 5**, dengan maksimum 9
bagian pada patch. Bagian mesh merupakan potensi submission per pass, bukan
hasil pengukuran draw call pada satu frame. Rig tetap 29 tulang; kenaikan
biaya bukan akibat jumlah tulang yang meningkat.

Sebagai skala saja, 22 kepala dengan biaya median berarti 29.876 versus
215.116 segitiga sebelum body dan pass tambahan. Ini bukan klaim bahwa semua
22 kepala selalu tergambar atau bahwa FPS turun dengan rasio yang sama.

### Kandidat paling berat

| Pemain dalam dataset runtime | Wajah | Rambut | Total kepala |
| --- | ---: | ---: | ---: |
| Jeremie Frimpong | 5.156 | 79.010 | 84.166 |
| Xavi Simons | 7.792 | 68.924 | 76.716 |
| Nathan Saliba | 5.156 | 69.633 | 74.789 |
| Roméo Lavia | 5.156 | 69.379 | 74.535 |
| Tammy Abraham | 4.500 | 55.066 | 59.566 |
| Kyle Walker-Peters | 4.500 | 42.746 | 47.246 |
| Jake O'Brien | 27.256 | 19.229 | 46.485 |
| Unai Simón | 27.172 | 19.090 | 46.262 |

Untuk pemain Barcelona dalam dataset ini: Balde **33.470**, Yamal **26.748**,
Koundé **25.114**, Raphinha **16.578**, dan Eric García **12.432** segitiga
wajah+rambut. Keanggotaan tim mengikuti roster proyek, bukan klaim transfer
atau keanggotaan liga saat ini.

Xavi Simons juga menjadi outlier vertex: **136.112 pada rambut**, atau
140.295 untuk kepala lengkap. Dump UE Viewer build 1590 melaporkan
`IndexCount=0` untuk mesh ini walaupun bagian render berisi 68.924 segitiga.
Auditor tidak menerima nol itu sebagai geometri kosong: ekspor glTF terpisah
memverifikasi jumlah accessor indeks dan ukuran buffer. Angka vertex hasil
cook dapat membesar karena pemisahan corner/normal/UV; tidak sama dengan
jumlah titik unik sebelum import.

## Mengapa dekat kamera dapat lebih berat

`hair_parts_tablet_ss` yang dipakai patch adalah material native **dua sisi**
dengan **BLEND_Masked**, clip value 0,333. Banyak lapisan kartu rambut dapat
menggambar piksel yang saling menutupi; dekat kamera, cakupan pikselnya lebih
besar. Ini konsisten dengan gejala dekat kamera, termasuk pada Night. Jumlah
segitiga tinggi, vertex hasil cook, dan bagian material juga meningkatkan
workload yang perlu diperiksa.

Ini belum membuktikan komponen mana yang paling dominan pada GPU Switch.
Karena mesh hanya punya satu LOD, data ini juga tidak mendukung penjelasan
bahwa file patch sedang berpindah ke LOD geometri lebih tinggi saat mendekat.
Detail tertingginya memang merupakan satu-satunya detail yang tersedia.

## Apakah memaksa pemain ke Low/Standard cukup?

**Belum cukup untuk menurunkan geometri real face yang sekarang.**

1. Factory memilih `face_high.fmdl` dan `hair_high.fmdl`. Import UE di
   `ue_prepare_realface.py` tidak membuat LOD tambahan; audit paket
   membuktikan hasil akhirnya memang satu LOD. Inventaris seluruh FMDL yang
   sudah diekstrak untuk 877 sumber konversi liga menemukan masing-masing
   877 `face_high` dan `hair_high`, plus 63 `oral`; tidak ada varian low/mid
   siap pakai pada sumber terpilih tersebut. Dua puluh aset Barcelona lama
   tidak termasuk cakupan inventaris sumber ini, tetapi termasuk audit PAK.
2. Native `UEPlayerModel::LoadImpl` memilih kelas actor berdasarkan quality.
   Vtable **APlayerActorHigh, APlayerActorLow, dan APlayerActorLowest** semuanya
   memakai `APlayerActor::LoadRealFace` pada virtual offset `0x630`. Pemilihan
   kelas actor yang lebih rendah tidak menyediakan file wajah ringan lain.
   Nama kelas Low internal bukan label Low di menu; quality 1/Standard memilih
   kelas tersebut, sedangkan quality 0 memilih Lowest.
3. `USkinnedMeshComponent::SetForcedLOD` membatasi permintaan pada jumlah LOD
   yang tersedia. Eksekusi fungsi ARM64 asli pada harness lokal membuktikan
   permintaan 2, 3, atau 99 pada mesh satu LOD tetap menghasilkan ForcedLOD=1
   (LOD0). Angka 0 berarti auto, bukan geometri paling ringan.

Override actor Standard khusus pemain mungkin mengurangi pekerjaan body atau
fitur rendering lain, tetapi **bukan pengganti pengurangan mesh wajah/rambut**.
Ia juga menyentuh jalur load async dan pemilihan body; perlu audit terpisah
sebelum diperluas dari override wasit yang sudah ada.

## Rekomendasi implementasi berikutnya

Prioritas pertama adalah **PAK real face Lite** dengan budget mendekati
native, yang tetap dipakai saat opsi grafis global High. Gunakan satu versi
mesh ringan dulu agar perbaikannya tidak bergantung pada hook per-frame atau
perubahan tracking kamera.

| Bagian | Target awal untuk uji |
| --- | --- |
| Wajah, mata, dan leher | sekitar 1.200–1.500 segitiga |
| Rambut dan kulit kepala | sekitar 300–500 segitiga; bentuk rumit dapat memakai sisa budget |
| Kepala lengkap | target 1.500–2.000; batas kandidat 2.500 |
| Bagian material | target 3; maksimum 4 jika kulit kepala perlu material terpisah |

Angka ini **budget kandidat**, bukan batas hardware yang telah diukur atau
jaminan 60 FPS. Kandidat yang tidak bisa mempertahankan bentuk/attachment
dalam budget harus ditahan untuk perbaikan, bukan otomatis dianggap lolos.

Automation yang disarankan:

1. Kurangi geometri di tahap offline, terutama lapisan rambut yang berlebihan.
   Decimation biasa tidak cukup bila bentuk rambut bertumpu pada puluhan ribu
   kartu; perlu mengurangi lapisan/kartu dengan menjaga siluet dan alpha atlas.
   Lindungi bukaan mata, batas leher, UV, dan skin weight hasil fitting.
2. Satukan bagian skin yang benar-benar memakai material/atlas sama dan bagian
   hair yang kompatibel. Tetap pisahkan mata serta material masked dari skin
   opaque. Audit jumlah vertex **setelah cook**, bukan hanya sebelum FBX.
3. Tambahkan gerbang budget pada hasil cook: segitiga, vertex, bagian material,
   rig, UV, kontinuitas mata/leher, dan kecocokan identitas. Cache key harus
   memasukkan profil budget dan versi simplifier agar hasil lama tidak terpakai
   sebagai output Lite. Pengolahan tetap lokal, tanpa API berbayar per pemain.
4. Mulai dengan canary Barcelona dan outlier Frimpong/Xavi Simons. Uji PAK
   penuh versus Lite dengan NRO, kamera, tim, stadium, dan quality yang sama;
   pisahkan varian pengurangan rambut dari wajah untuk menilai sumber biaya.
   Periksa permainan dekat kamera serta replay/selebrasi untuk seam dan siluet.
5. Setelah Lite diterima, pertimbangkan LOD tambahan untuk close-up/replay.
   UE mendukung pembuatan LOD, tetapi routing native dan sinkronisasi LOD ke
   parent/master pose harus diuji dahulu. Jangan menganggap penambahan LOD1
   saja otomatis membuat runtime memilihnya. Versi Lite satu LOD juga akan
   terlihat lebih sederhana pada close-up; itu tradeoff tahap pertama.

Referensi primer umum: [Epic — Using the Skeletal Mesh Reduction Tool,
UE4.27](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-the-skeletal-mesh-reduction-tool?application_version=4.27).
Kontrak setter/clamp untuk proyek ini diverifikasi terhadap source UE4.22
lokal dan library Mobile yang benar-benar digunakan, bukan diasumsikan dari
perilaku UE versi terbaru.

## Mengulang audit

`tools/audit_realface_performance.py` membaca daftar anggota PAK melalui repak
dan seluruh metadata LOD melalui UE Viewer. PAK native dan patch dipasang
sementara sebagai hard link di direktori terisolasi agar prioritas mount
tidak mencampur hasilnya. Output perlu berada pada volume yang sama dengan
PAK. Geometri/tekstur tidak disimpan pada laporan.

```powershell
python tools/audit_realface_performance.py `
  --native-pak <main-mobile.pak> `
  --patch-pak <league-faces-v24.pak> `
  --verification <VERIFICATION.json> `
  --repak <repak.exe> --umodel <umodel_64.exe> `
  --mobile-library dist/pes21_nx/libUE4.so `
  --output local-debug/realface-performance-audit
```

Laporan lokal berisi `report.json`, `players.csv` untuk semua 897 pemain,
dan metadata numerik tiap mesh native/patch. Hash PAK dan manifest serta
kelengkapan ID diperiksa sebelum laporan dibuat. Tidak ada PAK/NRO baru
yang dibuat oleh audit ini.

Validasi: **9 tes dan 18 subtes lolos**, mencakup metadata sintetis, beberapa
LOD, pasangan yang hilang, indeks 32-bit, manifest salah, dan eksekusi setter
LOD native. Kasus native dilewati dengan alasan jelas bila library atau
dependency lokal tidak tersedia.
