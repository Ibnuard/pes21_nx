# Retest HTTPS setelah deployment perbaikan v113

29 Oktober 2026 WIB. Endpoint yang diuji:
`https://wedreamku.my.id/footballnx/api/v1`.
Perilaku deployment setelah commit `8f7feee` diverifikasi memakai akun operator
TEST yang telah diizinkan. Empat temuan pada retest v113 sebelumnya **ditutup**.
Ada satu temuan tambahan pada error sesi kedaluwarsa; perbaikannya ada pada
source dalam commit laporan ini dan masih perlu deploy/retest.

## Hasil pada deployment

| Area | Bukti |
| --- | --- |
| Rekonsiliasi liga lama | Cycle 16 kini empat klub played=3, drawn=3, points=3; watermark Player Feed valid. |
| Replay join | Dua join liga baru beserta exact replay tetap TEST, satu receipt; masing-masing menambah tepat +1.500 cash dan +500 monthly PTS. |
| Clock | Revision 27 → 45 melalui 18 advance unik, disertai GET receipt dan POST replay. Tidak ada target mundur atau pipeline menggantung. |
| Scope W1/W2 | Registration sebelum/sesudah join mengirim schedule/standings kosong sampai draw. W2 tidak memakai fixture W1. |
| Liga baru | Cycle 18/W1 dan 19/W2 masing-masing satu manusia, tiga BOT, enam fixture. Seluruh 12 pertandingan ENDED mempunyai hasil dan klasemen yang sesuai. |
| Monthly podium | Poin akun 8.500 → 13.500: +1.000 partisipasi dan +4.000 dari dua podium juara. Poin podium masuk sesudah FT, tidak ditambah ulang saat Minggu. |
| NX Cash podium | Saldo sebelum Minggu 34.000 → 44.000, tepat +10.000 untuk dua juara. Replay dan pembacaan ulang setelah worker berjalan tidak menambah saldo/revision lagi. |
| News/history | 18 aktivitas minggu berjalan: 12 hasil dan enam leader round, ID unik, timestamp/W1/W2 valid. Riwayat masing-masing juara muncul sekali. |
| Playback | LIVE dan replay mengirim satu full bundle berisi 22 chunk; chunks/events identik. Tidak memerlukan stream. |
| Guard | Revision stale ditolak 409; token TEST dengan assertion PRODUCTION ditolak 403; halaman ranking invalid ditolak 400; snapshot halaman yang sama stabil. |

Parser/controller C dari client v113 menerima **184 payload, 0 penolakan**.
Dua respons Player Feed sebelum Match Day merupakan gate 409 yang diharapkan.
Dua tape diuji pada **1.322 posisi playback**: kesiapan frame, skor dan jumlah
touchline mengikuti posisi waktunya. Guard realm client tidak dilonggarkan.
Dokumen OpenAPI deployed juga mempunyai hash yang sama dengan source `8f7feee`;
ini verifikasi dokumen, bukan bukti hash binary yang berjalan.

## Temuan tambahan: error sesi TEST kedaluwarsa

GET `/club/profile` menggunakan token TEST lama yang masih dikenali server
tetapi access session-nya kedaluwarsa menghasilkan:

```json
{"error":{"code":"SESSION_EXPIRED"},"meta":{"environment":"PRODUCTION"}}
```

HTTP 401 benar, tetapi metadata realm salah. Payload aktual ini direproduksi
melalui `consume()` client C: muncul ENVIRONMENT MISMATCH sebelum cabang refresh
session, sehingga refresh yang seharusnya dicoba tidak berjalan.

`AuthMiddleware` sebelumnya baru memasang realm/domain clock **setelah** seluruh
validasi session dan assertion header. Perbaikan menyiapkan response context dari
session yang berhasil ditemukan di database sebelum mengembalikan 401/403.
AuthUser tetap hanya diberikan setelah semua validasi lolos. Realm tidak diambil
dari assertion header; token tidak dikenal tetap ditolak.

Tes PostgreSQL dengan dua database sintetis memeriksa expired/revoked session,
perubahan credential, akun disabled, assertion salah, session valid TEST dan
PRODUCTION, serta token tidak dikenal. Metadata TEST mempertahankan domain clock;
header TEST tidak bisa mengubah identitas realm token PRODUCTION. Tes auth dengan
race detector lulus. Perbaikan ini tidak membutuhkan schema atau NRO baru.

Acceptance setelah deploy commit ini: ulangi GET memakai token TEST kedaluwarsa
yang masih dikenali, pastikan HTTP 401/SESSION_EXPIRED dengan meta TEST dan clock
TEST; kemudian pastikan client masuk ke jalur refresh/relogin yang sesuai.

Verifikasi source tambahan: `go test -race -p 1 -timeout 240s ./...`, `go vet
./...` dan build binary lulus. Audit public-tree milik repository client masih
menandai empat file backend existing karena path instalasi server absolut:
`cmd/fnx-server/main.go`, `docs/RUNBOOK.md`, `internal/config/config.go`, dan
`internal/httpapi/routes.go`. Semua temuan tersebut sudah ada pada `8f7feee`;
perubahan auth/test/laporan ini tidak menambah path pribadi, key, atau binary.
Audit seluruh tree belum bersih dan perlu dirapikan pada pekerjaan konfigurasi.

## Batas pengujian

- Mutasi server hanya login TEST, dua join TEST, dan demo clock TEST. Tidak ada
  pembelian pack, redeem CDK, akun baru, atau mutasi realm PRODUCTION.
- Semua 12 skor liga baru 0–0. Feed kosong sah dan watermark telah diuji;
  kontribusi gol/assist positif belum dibuktikan melalui pertandingan live ini.
- Tidak ada pengujian Switch fisik, render atlas/portrait, atau perubahan NRO.
- Clock operator ditinggalkan pada hasil Minggu, revision 45, cycle 19,
  saldo TEST 44.000. NEXT_MILESTONE berikutnya menuju registration minggu baru.
- Raw token/response/tape dan executable harness tetap di direktori lokal
  ignored; tidak dimasukkan ke Git. Source tes menggunakan data sintetis.

Perbaikan auth dipush sebagai BlekjekSudo: [f65e2b6](https://github.com/BlekjekSudo/fnx_server/commit/f65e2b68b0730593c45177964e2da25c789b073b).
