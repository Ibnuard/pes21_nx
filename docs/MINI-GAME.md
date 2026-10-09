# MINI-GAME

Tanggal: 9 Oktober 2026  
Status: konsep untuk pengembangan berikutnya; belum diimplementasikan.

Dua ide mini-game untuk FootballNX adalah Football Triple Triad berbasis
kartu pemain dan Mini Soccer 6v6 di setengah lapangan. Prioritas yang
disarankan adalah Football Triple Triad karena data pemain, pemuatan portrait,
UI custom, dan input controller sudah tersedia. Mini Soccer memerlukan
pembuktian lebih lanjut pada engine pertandingan native.

Keinginan utama untuk mode kartu adalah UI yang sangat hidup atau "juicy"
serta pilihan bermain melawan pemain lain secara online. VPS yang tersedia
memiliki RAM 2 GB dan 2 core. Pembahasan ini disimpan sebagai konsep;
pengembangan dan deployment belum dimulai.

## Perbandingan konsep

| Konsep | Pengalaman bermain | Kesiapan dan ketergantungan |
| --- | --- | --- |
| Football Triple Triad | Pertandingan strategi singkat, menyusun deck, dan mengoleksi kartu pemain | Dapat memakai data serta portrait lokal melalui UI custom; aturan permainan, AI kartu, dan jaringan masih perlu dibuat |
| Mini Soccer 6v6 | Pertandingan sepak bola yang lebih padat di area kecil | Perubahan jumlah pemain dan posisi gawang harus diikuti aturan, AI, batas lapangan, serta kamera native |

## Football Triple Triad

Usulan permainan awal memakai papan 3×3 dan lima kartu per pemain. Setiap
kartu memiliki empat angka pada sisinya. Pemain bergantian meletakkan kartu;
angka yang lebih besar dapat merebut kartu lawan pada sisi yang berhadapan.
Fondasinya mengikuti [aturan dasar Triple Triad](https://na.finalfantasyxiv.com/lodestone/playguide/contentsguide/goldsaucer/tripletriad/).

Kartu menampilkan portrait, nama pemain, posisi, dan identitas klub. Empat nilai
dapat diturunkan dari kemampuan menyerang, bertahan, teknik, dan fisik.
Rumus konversi serta keseimbangannya belum ditetapkan. Pemain dengan rating
tinggi tidak harus unggul pada keempat sisi. Batas kekuatan total deck menjadi
usulan agar kartu pemain dengan rating lebih rendah tetap berguna.

Kartu mengikuti identitas pemain kanonik dan kebijakan BaseId proyek, dengan
mapping yang persisten. Native player ID adalah kunci penyimpanan engine,
bukan bukti identitas atau kepemilikan portrait. Portrait dan data game tetap
berasal dari runtime lokal yang dimiliki pengguna; payload tersebut tidak
masuk ke repository publik.

## Usulan dua mode bermain

| Mode | Cakupan awal |
| --- | --- |
| Vs CPU | Pertandingan offline, pemilihan deck sederhana, dan lawan komputer |
| Vs Player | Pertandingan online melalui VPS, dengan room code untuk mengundang teman |

Pembagian Vs CPU dan Vs Player online merupakan usulan awal dari pembahasan.
Aturan kartu digunakan bersama agar hasil perhitungan offline dan online
konsisten. Koleksi kartu, hadiah kemenangan, tantangan, dan turnamen dapat
ditambahkan setelah pertandingan dasarnya nyaman dimainkan.

## Arah UI dan animasi

Tampilan kartu mengikuti bahasa visual UI FootballNX yang sudah diperbarui.
Gerakan, perubahan warna, suara, dan feedback controller membantu pemain
memahami pilihan serta hasil setiap langkah.

| Interaksi | Efek yang diusulkan |
| --- | --- |
| Memilih kartu | Kartu terangkat, sedikit miring, dan bayangannya membesar |
| Memilih kotak | Kotak tujuan menyala; sisi kartu yang akan beradu diberi penanda |
| Meletakkan kartu | Kartu meluncur ke papan, disertai pantulan kecil dan suara benturan pendek |
| Merebut kartu | Kartu berputar, warna kepemilikan berubah, dan kilatan mengikuti arah serangan |
| Combo | Jika aturan combo ditambahkan, perebutan berantai memiliki tempo animasi dan suara yang meningkat |
| Menang | Skor bergerak, kartu pemenang ditonjolkan, dan partikel selebrasi muncul |

Portrait, tekstur, suara, dan animasi diproses di Switch. Server mengirim
kejadian permainan yang kemudian ditampilkan oleh client. Efek visual tidak
memerlukan pengiriman posisi animasi setiap frame. Kelancaran dan biaya efek
tetap perlu diukur pada Switch; belum ada target frame rate yang tervalidasi.

## PvP online dan VPS

VPS RAM 2 GB dengan 2 core dinilai masuk akal sebagai titik awal untuk
backend permainan kartu yang ringan. Kapasitas pemain bersamaan belum
ditetapkan dan harus diukur lewat pengujian beban pada VPS tersebut.
Bahasa backend, database, dan pustaka jaringan belum dipilih.

Client mengirim pilihan kartu dan kotak tujuan. Server memeriksa giliran,
kartu yang tersedia, legalitas penempatan, serta hasil perebutan, lalu
mengirim perubahan papan dan hasil pertandingan kepada kedua pemain.
Statistik dan aturan kartu harus mengacu pada katalog yang disepakati server.
Pola ini sesuai dengan [permainan bergiliran yang divalidasi server](https://heroiclabs.com/docs/nakama/concepts/multiplayer/authoritative/),
yang dapat memakai frekuensi pesan rendah. Referensi tersebut menjelaskan
arsitektur; penggunaan Nakama belum diputuskan.

Ilustrasi bandwidth dengan asumsi setiap pembaruan papan berukuran 2 KB:

`9 giliran × 2 pemain × 2 KB = sekitar 36 KB payload keluar dari server`

Angka itu hanya mencakup pembaruan papan satu pertandingan, bukan hasil
pengukuran. Koneksi awal, lobby, heartbeat, overhead protokol, dan reconnect
menambah trafik. Portrait serta tekstur kartu dimuat dari data lokal dan
tidak dikirim ulang untuk setiap langkah.

Fondasi jaringan yang perlu disiapkan:

- Versi katalog kartu dan aturan yang sama agar kedua pemain menghitung
  statistik dari acuan yang konsisten.
- Nomor urutan langkah agar pengiriman ulang tidak menggandakan gerakan.
- Snapshot pertandingan dan reconnect agar koneksi yang terputus dapat
  melanjutkan keadaan papan yang benar.
- Penanganan giliran, timeout, dan putus koneksi dengan hasil yang ditentukan
  server.

Wrapper saat ini belum memiliki modul online khusus permainan kartu.
Fitur tersebut perlu dibangun dan diuji bersama room code serta pemulihan
koneksi.

## Mini Soccer 6v6

Konsepnya adalah memakai setengah lapangan dengan posisi gawang disesuaikan
dan enam pemain per tim. Ukuran area bermain, orientasi lapangan, serta aturan
detailnya belum ditetapkan.

Pipeline formasi saat ini mengasumsikan sebelas pemain dengan satu penjaga
gawang. Kelayakan 6v6 perlu dibuktikan pada engine native. Posisi gawang baru
juga harus diikuti deteksi gol, perilaku kiper, AI pemain, kickoff, bola keluar,
set piece, dan kamera.

Prototipe pertama harus membuktikan enam pemain aktif per tim, gol yang
terdeteksi pada posisi gawang baru, serta AI dan kiper yang menggunakan area
bermain baru. Hasil eksperimen itu menentukan cakupan implementasi penuh.

## Urutan pengembangan yang disarankan

1. Buat satu pertandingan kartu lengkap dengan pemilihan deck, papan, aturan
   dasar, Vs CPU, dan feedback visual serta suara.
2. Gunakan aturan yang sama pada server, lalu tambahkan Vs Player melalui
   room code.
3. Uji konsistensi katalog, reconnect, langkah duplikat, performa UI Switch,
   dan kapasitas VPS.
4. Kembangkan koleksi, hadiah, tantangan, dan turnamen setelah permainan
   dasarnya stabil.
5. Lakukan prototipe kelayakan Mini Soccer sebelum menentukan implementasi
   mode 6v6 secara penuh.

Rumus nilai kartu, batas kekuatan deck, aturan lanjutan, progres koleksi,
dan kapasitas online tetap menjadi keputusan desain berikutnya.
