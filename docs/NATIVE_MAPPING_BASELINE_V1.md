# Native Mapping Baseline V1

Status per 1 September 2026: **diterima sebagai baseline awal untuk native
live-play**, dengan set-play dan visual power gauge masih menjadi backlog.

Paket immutable ada di
`local-debug/native-pad-v1-baseline-20260901/install/pes21_nx.nro`.
SHA256-nya `f2e52b1e30983d26a747d5d11c68624f2743ad0dcfcfcf6d73e6ad3f17b0bcb0`,
persis sama dengan Native Pad Lab V2 yang diuji di Switch. Karena binary sama,
pengguna yang masih memakai V2 tidak perlu menyalin file lagi.

## Hasil yang sudah lolos

Live-play sudah berjalan melalui history input dan ThinkUnit native. Pengguna
mengonfirmasi controlled/finesse shoot R2, match-up L1 + X, dan lofted through
ball L1 + Segitiga. Kombinasi modifier ini tidak dapat dijelaskan hanya oleh
mapping tombol virtual tunggal, sehingga menjadi validasi perangkat terhadap
route native yang dibuat.

Second-player pressure belum diberi status lulus perangkat. Route FriendPress
native sudah dimasukkan, tetapi aksi pertahanannya masih harus diuji terpisah.

## Diagnosis kekurangan yang dilaporkan

1. **Power gauge shoot** - unit Shoot native dan jalur kick-gauge ada, tetapi
   `MobileShoot::Update2DInfo` adalah produsen visual mobile. V1 mengganti
   MobileShoot sepenuhnya, jadi tembakan tetap bekerja tanpa presentasi gauge.
   Kebijakan Player Cursor tidak menghapus slot shoot gauge.
2. **Goal kick dan corner** - scheduler set-play masih memilih
   `MobileSetplayKick`, yang membaca `ButtonObject`, swipe, dan swipe vector.
   Raw left stick native tidak otomatis masuk ke konsumer itu.
3. **Throw-in** - konteks out-of-play masih bergantung pada
   `MobileOutOfPlay`; unit native `ThrowinBodyAngleRotation` ada tetapi belum
   diroute sebagai penggantinya.
4. **Corner strategy** - `CornerKickTactics` native benar-benar ada dan membaca
   click/press tombol arah. Fungsi ini belum dijadwalkan oleh daftar V1, jadi
   arrow option console belum aktif.

Masalah set-play bukan tanda bahwa live-play masih memakai touchscreen. Justru
V1 sengaja mematikan fallback touch selama Native Lab aktif; akibatnya cabang
set-play yang belum dikonversi tidak mempunyai input sama sekali.

## Aturan iterasi berikut

- Baseline V1 dan pitch visual-v14 tidak ditimpa.
- Perbaikan dibuat sebagai kandidat baru: pertama pertahankan gauge visual,
  lalu route goal kick, corner, dan throw-in per konteks.
- Corner tactics diaktifkan setelah input dasar corner berhasil agar penyebab
  regresi mudah dipisahkan.
- Exhibition tetap memakai jalur stable yang ada.

