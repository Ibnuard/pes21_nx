# Retest deployment 25b61f1 dan build Switch

29 Oktober 2026 WIB. Endpoint HTTPS yang diuji:
`https://wedreamku.my.id/footballnx/api/v1`.
Retest memakai sesi operator TEST yang telah diizinkan; patch backend
[25b61f1](https://github.com/BlekjekSudo/fnx_server/commit/25b61f1f75832500eeb72f50372927439b7b673a)
sudah menunjukkan perilaku refresh yang benar pada deployment ini.

## Hasil API dan controller client

- Access token TEST lama: HTTP 401 SESSION_EXPIRED, meta TEST/domain clock TEST.
- Satu refresh token TEST yang sah: HTTP 200; data.environment dan
  meta.environment sama-sama TEST, demo_time=true, test_clock.revision=45.
  Waktu domain refresh sama dengan bootstrap. Token baru berbeda dari token
  lama dan bisa membuka endpoint terlindungi dengan assertion TEST.
- Compatibility gate deployed cocok dengan versi online 1.0.0, schema 1,
  hash katalog client dan runtime pair e861c583ec78e9ae; maintenance=false.
- Smoke 14 endpoint HTTP 200: bootstrap, status, profile, schedule, standings,
  Player Feed, news, Current/Past Season, champions, squad, Game Plan, offers,
  dan pending. Assertion PRODUCTION pada access TEST ditolak HTTP 403 dengan
  envelope TEST.
- GET playback pertandingan ENDED mengirim satu full bundle 22 chunk.
  Parser C client menerima 13 payload, 0 ditolak. Satu tape diperiksa pada
  661 posisi waktu: frame siap, skor dan touchline mengikuti posisi playback.
- Respons 401 dan refresh yang diambil dari server diproses oleh consume()
  controller C: refresh mempertahankan autentikasi/realm TEST, capability
  ONLINEDEV dan halaman semula; safe GET dilanjutkan. Tidak kembali ke login.
  Request lanjutan pada harness sengaja tidak menghubungi server; access baru
  sudah dibuktikan terpisah melalui 14 GET HTTPS aktual.
- Suite controller client: 50 tes lulus.

Clock tetap revision 45, cycle 19, LEAGUE_END. Wallet tetap 44.000 NX Cash,
version 13. Keempat klub played=3; schedule sesuai current cycle.

## Build dan distribusi

Build memakai build-wsl.ps1 dengan Jobs=1/LtoJobs=1 dan input runtime v113
existing: pair e861c583ec78e9ae, dummy OBB 53.248 byte, selector/roster,
badge atlas, katalog Master League dan commentary yang saling berpasangan.
Build selesai dan ikon NRO lolos pemeriksaan byte-for-byte. ELF AArch64
mempunyai tiga PT_LOAD yang cocok dengan NRO; 238 hash source/build cocok.

- NRO: 86.778.783 byte.
- SHA256 NRO: `87bd936cec2b661cb06131d55a6746e891658d7edfffb9d50b84ef89aa20cadf`.
- Build ID: `822d88fd366b7050333a48c9d7636703a7cd4060`.
- Paket: `D:/PESNX-Cache/Deliveries/FootballNX27-v113-ONLINE-VERIFIED-SIAP-COPY.zip`.
- ZIP: 46128690 byte, SHA256
  `74a4bf19ca33b8f489e4efb75f0b25ec0ecd2bca15c7862b7009214284ee6bbc`.

Paket hanya berisi BACA-DULU.txt, VERIFICATION.json dan
switch/pes21_nx/pes21_nx.nro. Isi ZIP dan hash setiap entry sudah diperiksa.
Hasil rebuild identik dengan NRO v113 sebelumnya karena source client tidak
berubah; perbaikan deployment ini berada di backend. Runtime aktif/SaveData
lokal tidak diganti. Belum ada acceptance Switch fisik.

## Batas tes

Tidak ada advance clock, join liga baru, pembayaran pack, redeem CDK, akun
baru atau mutasi PRODUCTION dalam retest ini. Mutasi server hanya satu
refresh sesi TEST. Refresh token lama tidak di-replay setelah HTTP 200.
Pengujian penuh clock dua liga/18 advance sebelumnya tercatat pada
[retest 8f7feee](MANAGER_BACKEND_RETEST_8F7FEEE.md); tidak diulang dalam tes auth.
Tidak ada tes Switch fisik atau verifikasi render portrait/atlas di perangkat.
Raw response/token/tape dan executable harness disimpan dalam local-debug
ignored, tidak dimasukkan ke Git ataupun paket distribusi.
