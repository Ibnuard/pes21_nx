# Retest deployment f65e2b6 dan koreksi refresh sesi

29 Oktober 2026 WIB. Pengujian HTTPS terhadap
`https://wedreamku.my.id/footballnx/api/v1`, menggunakan akun operator TEST
yang sudah diizinkan. Ini melanjutkan [retest 8f7feee](V113-LIVE-RETEST.md).

## Hasil deployment

Perbaikan error sesi kedaluwarsa pada `f65e2b6` **sudah terverifikasi live**.
Dua access token TEST lama menghasilkan HTTP 401 `SESSION_EXPIRED` dengan
`meta.environment: TEST` dan domain clock TEST. Respons aktual dimasukkan ke
`consume()` controller C client: guard realm lolos dan cabang refresh safe GET
dijalankan sekali, dengan request squad disimpan untuk dilanjutkan.

Smoke test 14 endpoint berhasil HTTP 200: bootstrap, status liga, profil,
schedule, standings, Player Feed, Club Feed, Current/Past Season, champions,
squad, Game Plan, shop offers, dan pending pack. Dua belas payload yang mempunyai
parser pada harness client diterima seluruhnya, **12 accepted / 0 rejected**.
Assertion PRODUCTION pada access token TEST ditolak HTTP 403
`ENVIRONMENT_MISMATCH` dan envelope tetap TEST.

Clock tetap revision 45, cycle 19, phase `LEAGUE_END`; wallet tetap 44.000
NX Cash, version 13. Schedule hanya memuat cycle saat ini dan keempat klub
memiliki played=3. Tidak ada clock advance/join baru pada retest ini;
verifikasi penuh 18 advance dan dua liga baru tercatat pada laporan sebelumnya.

## Temuan baru: response refresh kehilangan realm

POST `/auth/refresh` memakai refresh token TEST yang sah menghasilkan HTTP 200:

```json
{
  "data": {
    "environment": "",
    "capabilities": {"demo_time": false, "promotion_codes": true},
    "test_clock": null
  },
  "meta": {"environment": "PRODUCTION"}
}
```

Token baru tetap milik TEST: GET `/me/bootstrap` dengan access token baru dan
assertion TEST berhasil, realm TEST, demo_time=true, clock revision 45.
Jadi ini kesalahan DTO/envelope refresh, bukan perpindahan data ke PRODUCTION.
Respons aktual juga diuji melalui `consume()` controller C client: autentikasi
dibersihkan dan halaman kembali ke login. Jadi pemulihan otomatis masih gagal
pada deployment ini walaupun guard error 401 sudah diperbaiki.

Penyebab source: `handleRefresh` melakukan query environment/role melalui
`tx.QueryRowContext` **sesudah `tx.Commit()`**. Query gagal `sql.ErrTxDone`,
error diabaikan, environment kosong dan envelope memakai default PRODUCTION.
Rotasi token telanjur tersimpan. Refresh token lama tidak dipakai ulang pada
server karena replay token ROTATED memang mencabut sesi akun.

## Perbaikan source dalam commit laporan ini

- Environment/role dan status account/session dibaca bersama token yang dikunci,
  sebelum commit. DTO dan envelope memakai realm akun yang tersimpan di server.
- Header environment hanya mengurutkan pencarian di dua DB. Token dapat
  ditemukan tanpa assertion; assertion salah ditolak 403 sebelum rotasi.
- Clock TEST/revision dibaca dalam transaksi sebelum token diterbitkan. Waktu
  mengikuti clock domain yang berjalan saat ada broadcast aktif.
- Session revoked, account nonaktif, credential version berubah, dan refresh
  kedaluwarsa ditolak tanpa mengubah token. Access token yang sekadar kedaluwarsa
  tetap dapat diperbarui selama session dan refresh token sah.
- Error pembuatan token, update rotasi, dan commit revocation diperiksa.
  Update session, rotasi token lama, dan token baru tetap satu transaksi.
- Guard token reuse tetap mencabut sesi akun; tidak ada pengecualian client.

Tes regresi PostgreSQL memakai **dua database sintetis terpisah**. Sebelum patch,
kesembilan kasus utama gagal, termasuk revoked/disabled/credential berubah yang
masih mendapat HTTP 200. Sesudah patch tes fokus dengan race detector lulus:
TEST/PRODUCTION, tanpa assertion, dua mismatch assertion, revoked session,
credential berubah, account disabled, dan refresh expired. Juga diuji token
asing, persistensi rotasi, access baru terikat ke akun/realm yang benar, access
lama ditolak, serta reuse token lama mencabut access yang baru diterbitkan.

Verifikasi source lulus dengan Go 1.26.0 dan PostgreSQL lokal 18.6:
`go test -race -p 1 -timeout 240s ./...`, `go vet ./...`, dan
`go build -o bin/fnx-server ./cmd/fnx-server`. Package HTTP API dijalankan
ulang; package yang tidak berubah dapat memakai cache Go dari verifikasi
sebelumnya. Tidak ada integrasi PostgreSQL yang dilewati karena DSN tidak ada.

Patch sudah dipush sebagai BlekjekSudo ke main: [25b61f1](https://github.com/BlekjekSudo/fnx_server/commit/25b61f1f75832500eeb72f50372927439b7b673a).

## Deployment dan acceptance

Perbaikan refresh ini perlu deployment backend berikutnya; **belum dinyatakan
lulus di server**. Tidak membutuhkan migrasi schema atau NRO baru. Setelah
deploy, gunakan sesi TEST yang sah dan lakukan satu refresh, lalu pastikan:

1. HTTP 200, `data.environment` dan `meta.environment` sama-sama TEST.
2. `capabilities.demo_time=true`, `test_clock.revision` sesuai bootstrap, dan
   `server_now_ms` mengikuti clock TEST.
3. Access token baru berhasil membuka bootstrap/profil dengan assertion TEST.
4. Client dapat melanjutkan safe GET setelah access token expired.

Simpan token baru untuk percobaan selanjutnya. Jangan mengulang refresh token
lama setelah respons 200; endpoint ini memakai rotasi dengan deteksi reuse.

## Batas pengujian

- Satu mutasi server: refresh sesi operator TEST. Tidak ada perubahan data
  PRODUCTION, pembelian pack, redeem CDK, atau pembuatan akun.
- Tidak ada tes Switch fisik, render portrait/atlas, atau perubahan client/NRO.
- Tidak mengulang pengujian simulasi/gol positif pada retest auth ini.
- Raw token, response API dan executable harness disimpan lokal dalam direktori
  ignored. Source tes hanya berisi data sintetis.
- Audit public-tree seluruh backend masih menandai empat path instalasi absolut
  existing di `cmd/fnx-server/main.go`, `docs/RUNBOOK.md`,
  `internal/config/config.go`, dan `internal/httpapi/routes.go`. Temuan tersebut
  sudah ada pada base `f65e2b6`; patch ini tidak menambah path privat atau payload.
