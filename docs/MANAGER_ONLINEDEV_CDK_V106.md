# ONLINEDEV per akun dan promotion CDK — kontrak v106

28 Oktober 2026. Addendum normatif untuk
[backend plan](MANAGER_BACKEND_HANDOFF_V1.md) dan
[review deployment](BACKEND-REVIEW.md). Target tetap Go, MySQL, Docker,
Ubuntu 2 CPU/2 GB. **Kontrak baru ini belum tersedia di OpenAPI deployment
yang diperiksa pada v106.** Source Switch sudah mempunyai consumer dan tes
synthetic; jangan menganggap endpoint berikut sudah di-deploy.

Update retest v10728 Oktober: empat endpoint sekarang di-deploy, context realm
dan redeem CDK nyata lolos. Namun clock SUCCEEDED sampai Minggu belum memproses
registration/BOT/fixture/reward; lihat [temuan P1 terkini](BACKEND-REVIEW.md).
Pernyataan belum tersedia di atas adalah keadaan saat v106 ditulis, bukan status
deployment v107. Kontrak pipeline dalam dokumen ini tetap target yang wajib.

Retest v108: BOT/fixture/hasil/payout sekarang lolos pada skenario yang dicoba.
Read rekaman TEST belum mengikuti clock yang sama dan rotasi W2/minggu berikutnya
belum benar; daftar pekerjaan aktual berada di bagian v108 pada review.

## 1. Keputusan produk

- Login tetap satu layar User ID + PIN dan satu API origin. Operator menyediakan
  **satu akun DEV**, misalnya reserved User ID `fnx_dev`. Setelah login berhasil,
  server mengembalikan `environment: TEST`; client otomatis menjadi ONLINEDEV.
  Tidak ada pilihan TEST pada login, PIN khusus yang tertanam di NRO, atau
  pencocokan string `dev` di client sebagai pemberi hak.
- Akun biasa selalu PRODUCTION. Account yang sama tidak boleh berpindah realm
  lewat request/header. Akun DEV mempunyai club, starter canonical, collection,
  wallet, packs dan liga TEST sendiri. Saldo TEST bukan saldo production.
- ONLINEDEV memanggil API nyata untuk seluruh alur. `Y DEMO TIME` pada hub TEST
  membuka `NEXT MILESTONE` dan `FINISH THIS REAL WEEK`. Hasil tetap dihitung
  simulator backend yang sama, dengan parameter/aturan yang sama.
- DEV OFFLINE dan secret Main Menu ZL+ZR+Y dua detik tetap tersedia tanpa koneksi.
  Tidak mengirim save/score/cash/clock lokal ke API.
- Shop `X PROMOTION CODE` menerima purchased CDK: **satu kode sekali pakai
  memberikan tepat 5.000 NX Cash**. Beberapa CDK berbeda boleh dimiliki/redeem
  oleh akun yang sama. Tidak mengimplementasikan checkout/pembayaran CDK di NRO.
  Kode boleh dijual dan ditukar sebelum update berikutnya; jangan mewajibkan
  versi client masa depan hanya untuk redeem kode yang sudah aktif.

## 2. Routing account dan isolasi data

Satu origin tetap `https://wedreamku.my.id/footballnx/api/v1`. Auth registry
mengikat normalized user_id unik global ke credential/PIN hash, subject ID,
realm immutable dan account ID realm. Login/refresh hanya meresolusikan mapping
server ini. Public registration menolak semua reserved DEV IDs, tanpa mengungkap
PIN/keberadaan akun. Provision akun DEV lewat CLI/operator secret, tidak lewat
public register atau flag `is_dev` dari client. Jangan commit credential seed.

Access/refresh token dan session family mengikat subject, environment, audience,
expiry, scopes. Default account role `PLAYER`; DEV role `TEST_OPERATOR`, scope
`test.clock.advance`, hanya pada TEST. Server memvalidasi role tersimpan dan
revocation, bukan membaca klaim client yang tidak ditandatangani. Refresh tidak
boleh mengganti environment; ganti realm berarti logout dan login akun lain.

Gunakan **dua database MySQL** dalam satu instance untuk batas RAM:
`fnx_production` dan `fnx_test`, schema/migration identik tetapi DB users dan
grants berbeda. Auth registry terpisah dan hanya menyimpan routing/auth, bukan
wallet liga. Scope DB connection dipilih sekali oleh authenticated principal;
repository tidak menerima nama database dari HTTP parameter. TEST worker hanya
memegang credential TEST. Production worker tidak mempunyai virtual-clock
dependency atau hak menulis TEST, begitu pula sebaliknya.

Seluruh mutable data terpisah: clubs, wallets/ledger, player instances, starters,
squads/plans/drafts, offers/purchases/pending/grants, cycles/entries/BOTs,
fixtures/tapes/events/reports, news, rewards/RP/honours, idempotency/outbox/jobs,
cache keys, object-storage prefixes, scheduler leases dan operation receipts.
Catalog canonical read-only boleh dibagi jika hash/version sama. Jangan copy
wallet/grant/hasil nyata ke TEST. IDs antar DB boleh sama; setiap cache, URL
authorization dan journal harus mengikat realm+subject/owner, bukan numeric ID
saja. TEST news/ranking/champions tidak muncul di production.

Client mengirim `X-FNX-Environment: TEST|PRODUCTION` setelah autentikasi sebagai
**assertion**, bukan selector privilege. Jika berbeda dari token, tolak403
`ENVIRONMENT_MISMATCH` sebelum memilih repository. Header tidak pernah mengubah
hak token. Request clock dengan token production ditolak403, bahkan bila memakai
User ID DEV, header TEST, path ID TEST atau body `environment: TEST`.

## 3. DTO auth, bootstrap dan envelope

Tambahkan pada **data** login, refresh, bootstrap (field lama tetap):

```json
{
  "environment": "TEST",
  "capabilities": {"demo_time": true, "promotion_codes": true},
  "test_clock": {"revision": 1}
}
```

TEST revision uint32 positif, monoton; capability `demo_time` hanya berasal dari
scope TEST_OPERATOR. Production wajib mengembalikan `environment: PRODUCTION`,
`demo_time: false`, `test_clock: null`; promotion_codes true bila redeem siap.
TEST juga boleh false bila operator dicabut/dinonaktifkan. Minimum entries tetap4.
Bootstrap mengembalikan account/club/wallet/league/pending seperti kontrak lama.
Semua JSON envelope, termasuk error dan status job, memuat:

```json
{"meta":{"environment":"TEST","server_now_ms":1792976400000,
         "real_server_now_ms":1793160000000,"online_version":"1.0.0",
         "api_schema_version":1}}
```

`server_now_ms` adalah **waktu domain liga realm**: virtual TEST, UTC nyata
PRODUCTION. Fixture kickoff, watermark, cutoff, pack validity, news/reward/RP
publication memakai clock domain yang sama; jangan campur real/virtual di domain.
`real_server_now_ms` untuk diagnostik aman; expiry access/refresh, throttles,
lease, retry/backoff, TLS dan job timeout selalu memakai real time. Client
menggunakan monotonic time untuk TTL auth dan polling agar maju seminggu tidak
membuat token langsung kedaluwarsa. Binary chunks tetap array seperti kontrak
lama; authorization realm diperiksa server sebelum membuka blob.

Transisi deployment: field baru yang belum ada boleh diperlakukan client v106
sebagai legacy PRODUCTION dengan **kedua capability mati**. TEST tidak boleh
memakai fallback ini: login/refresh membutuhkan context lengkap dan meta TEST;
bootstrap/reply TEST yang kehilangan/mengganti realm ditolak sebelum publish
wallet atau data. Sesudah migrasi, semua endpoint wajib field eksplisit di schema.
Tidak perlu menaikkan online version untuk penambahan field opsional ini, selama
semantik client1.0.0 tetap kompatibel. Reserve capability sebelum mengaktifkan UX.

## 4. Clock TEST dan worker

Bootstrap TEST baru dimulai pada Senin00:00 Asia/Jakarta yang disediakan operator,
bukan menyunting jam OS/container. Simpan anchor virtual + anchor real UTC,
revision dan lease dalam MySQL; normalnya TEST berjalan1x, dan advance hanya
melompat maju. Tidak ada endpoint arbitrary set-time, rewind, set-result atau
set-cash. Reset TEST/admin reseed di luar NRO memerlukan revoke sessions,
namespace/epoch baru dan prosedur operator; jangan reset revision menjadi1 pada
sesi lama dengan account ID yang sama.

`NEXT_MILESTONE` memilih milestone **strictly after** clock saat request:
registration close/autofill, hari preparation, first kickoff, halftime, fulltime,
kickoff berikutnya, registration W2, preparation W2, match W2, Sunday settlement,
lalu registration Senin berikutnya. Pakai jam kalender di §7 plan; tidak mengubah
durasi tape2x300000+60000ms atau jadwal production.
`FINISH_WEEK` menargetkan selesai Sunday settlement minggu TEST saat ini. Bila
minggu itu sudah settled, no-op receipt sukses dengan revision baru sekali;
bukan otomatis melompati/mendaftarkan liga minggu depan. Tidak auto-register
W2 atau menggandakan bonus; untuk menguji kedua liga, gunakan NEXT_MILESTONE
dan Join saat Senin serta Kamis sebelum Finish Week. Join memakai endpoint
`POST /league/join` lama dan aturan bonus unik+1500/cycle.

Advance harus menjalankan **pipeline domain production yang sama**: close
registration, H0 empty/H1..3 BOT fill-to4, legal groups, snapshot/roster lock,
deterministic compute+seal, publish sesuai waktu virtual, results, Sunday rewards,
RP14day reset, permanent honours dan outbox. Jangan hanya mengganti field phase,
menulis skor contoh, atau memberi hadiah langsung dari controller clock. Tape
yang sudah sealed tetap immutable. Settle W1/W2 sekali dan rank BOT tetap resmi.

Satu worker TEST, bounded queue dan satu clock job in-flight; satu fixture
compute per saat. Jangan membuat worker/video stream baru per penonton.
Advance cepat berarti melewati waktu tunggu kalender; compute tetap perlu
diproses. Go handler mengembalikan202 cepat, worker boleh butuh beberapa detik.
Worker mengulang milestone sampai target; tiap langkah durable/idempotent dan
fenced lease. Setelah crash, resume langkah tersimpan; jangan kembali ke clock
awal atau compute ulang sealed tape. GET/POST status tidak membuat job baru.
Saat job RUNNING, tahan mutation interaktif TEST dengan423 `TEST_ADVANCE_BUSY`
kecuali refresh/logout/recovery read. Bootstrap/status boleh melaporkan last
committed checkpoint; jangan mengklaim SUCCEEDED sebelum seluruh target selesai.
Kegagalan parsial tidak rollback ledger yang sudah sah: tandai FAILED dengan
checkpoint aktual, lalu bootstrap menampilkan revision/state aktual. Job retry
memerlukan rule resume yang eksplisit, bukan menggandakan side effect.

### API clock yang dikonsumsi client

`POST /dev/clock/advance`, Bearer TEST_OPERATOR, wajib Idempotency-Key UUID:

```json
{"action":"NEXT_MILESTONE","expected_revision":1}
```

Action enum `NEXT_MILESTONE|FINISH_WEEK`, revision wajib. Tidak menerima timestamp,
score, balance, account ID, realm atau amount dari client. Scope/token/realm
guard dijalankan sebelum claim key. Atomic CAS revision dan unique in-flight
clock lock; request revision stale409 `REVISION_CONFLICT`, tanpa job baru.
**Replay key/body dicek sebelum CAS** agar request yang telah selesai tidak
menjadi conflict hanya karena revision sekarang berubah. Key sama/body berbeda
409 `IDEMPOTENCY_CONFLICT`. Dua key dengan base revision sama: maksimal satu
diterima; lainnya409/423. Expected revision bukan clock yang diinginkan.

Status202 PENDING/RUNNING atau200 SUCCEEDED, contoh final:

```json
{
  "data": {
    "environment":"TEST","account_id":42,
    "idempotency_key":"00000000-0000-4000-8000-000000000001",
    "state":"SUCCEEDED","clock_revision":2,
    "test_now_ms":1793548800000
  },
  "meta":{"environment":"TEST","server_now_ms":1793548800000}
}
```

Semua state memuat environment, account_id dan idempotency_key yang sama dengan
owner operation. SUCCEEDED revision > expected_revision; now akhir target,
tidak wajib sama persis dengan meta sekarang saat lookup ulang. Receipt yang
lebih lama dari bootstrap terbaru tetap menyelesaikan intent lama, tanpa
menurunkan revision atau clock client. FAILED juga
mengembalikan error_code/checkpoint/revision aktual, tanpa berpura-pura sukses.
`GET /dev/clock/operations/{idempotency_key}` mengembalikan DTO sama; hanya owner
TEST_OPERATOR,404 `OPERATION_NOT_FOUND` untuk key yang belum diterima. Hasil
committed tidak boleh hilang menjadi404. Retain receipt/tombstone durable, jangan
TTL-cache sebagai satu-satunya evidence. Missing auth401; PRODUCTION403;
capability disabled403; rate-limit429 real-time dengan Retry-After.

Client menulis intent key/body/realm/account/origin ke SD sebelum POST, menahan
input selama loading, lalu poll status maksimal1request/detik. Lebih dari60detik
memberi popup dan menyimpan recovery; server job tetap berjalan. Timeout,
lost ACK/restart → lookup key yang sama. Bila benar-benar belum diterima,
`RETRY SAME OPERATION` memakai key/body yang persis sama. Tidak membuat key baru
untuk operasi yang statusnya belum jelas. Sukses menghapus intent, membuang cache
fixture/frame/event/watermark lama dan mengambil bootstrap baru dari server.

## 5. Redeem promotion code / CDK

Helper `X PROMOTION CODE` ada di Shop. Jika capability mati, popup belum tersedia.
Jika aktif, halaman berisi Enter Code dan Redeem Code; software keyboard menerima
ASCII letters/digits, spasi dan hyphen. Normalisasi server dan client identik:
hapus ASCII space/hyphen, uppercase ASCII, hasil12–32 alphanumeric, raw input
maksimal64bytes/body512bytes. Tolak
control/newline, Unicode lookalikes, tanda lain dan hasil berlebih. Kode mint
baru sebaiknya26 karakter base32 CSPRNG (>=128bit entropy), tanpa ambiguitas.
Jangan memakai user_id, counter, UUID pendek atau checksum saja sebagai kode.

`POST /promotions/redeem`, Bearer, wajib Idempotency-Key UUID:

```json
{"code":"ABCD1234EFGH5678"}
```

Contoh di atas synthetic, bukan kode valid. Body tidak menerima amount/currency/
account/environment. Nilai credit selalu di campaign server, dibatasi CHECK5000.
Kodemu sendiri boleh dipakai di TEST hanya bila mint dalam TEST; production code
tidak boleh habis/terkredit ketika dicoba dengan DEV, begitu pula sebaliknya.
Jangan menggunakan shared production redemption table untuk TEST.

200 SUCCEEDED atau202 PENDING, DTO final yang wajib:

```json
{
  "data": {
    "state":"SUCCEEDED","environment":"PRODUCTION","account_id":42,
    "idempotency_key":"00000000-0000-4000-8000-000000000002",
    "redemption_id":71,"currency":"NX_CASH","amount":5000,
    "wallet":{"balance":10000,"version":3}
  },
  "meta":{"environment":"PRODUCTION","server_now_ms":1793160000000}
}
```

PENDING juga wajib environment/account_id/idempotency_key. `redemption_id` positif,
wallet.balance integer0..INT64_MAX, wallet.version uint32 positif. Semua amount
integer; bukan float. `GET /promotions/operations/{idempotency_key}` mengembalikan
receipt/status sama, hanya owner/token realm sama.404 `OPERATION_NOT_FOUND`
berarti belum diterima; jangan hilangkan committed receipt saat cache restart.
Lookup harus tetap diizinkan ketika campaign/shop berakhir, dan transaksi
recovery read tidak boleh dihalangi gate future-version/offer yang tidak relevan.

Tolak invalid/unavailable/already-used-other-account secara generik422
`INVALID_CODE|CODE_UNAVAILABLE`; expired/not-active422 `CODE_EXPIRED|CODE_NOT_ACTIVE`.
Tidak mengembalikan username penerima lain, raw code, nilai PIN atau data batch.
Throttle real-time per account/IP + global budget,429; unknown transport/5xx tidak
boleh dianggap redemption gagal. Disabled403; wrong realm403; key body conflict409.
Error terminal yang menjamin **tidak ada credit** ditulis sebagai durable operation
outcome juga. Lookup outcome gagal boleh mengembalikan HTTP/code terminal yang
sama, bukan sukses kosong; client dapat replay POST key sama untuk menyelesaikan.

Transaksi MySQL: lookup durable idempotency receipt dan request hash → lock
voucher → validate realm/batch/activation/expiry → claim unik voucher → lock wallet
→ ledger CREDIT5000 dengan source CDK/redemption ID → wallet+version → redemption
receipt+outbox → COMMIT. Semua atau tidak sama sekali. Notification/outbox tidak
menjadi syarat commit kedua. Unique voucher redemption dan unique ledger source
mencegah doublecredit walau key berbeda, dua perangkat atau proses restart.

Jika kode sama dipakai lagi oleh pemilik yang sama, kembalikan redemption_id
asli tanpa credit baru; bind receipt baru ke key request sekarang. Snapshot wallet
receipt lama boleh ber-version lebih kecil dari wallet aktual. Client tidak boleh
menurunkan wallet berdasarkan receipt lama: setelah sukses, fetch bootstrap
terbaru, lalu tampilkan popup5000. Beda akun menerima unavailable. Revoke batch
tidak boleh menghapus ledger/receipt sah; chargeback/refund adalah workflow
operator terpisah dan diaudit, bukan delete credit diam-diam.

Intent redemption di SD berisi raw code hanya selama transaksi belum terselesaikan,
beserta key/body/realm/account/origin; anggap privat, jangan masukkan log,
screenshots debug, telemetry atau backup publik. Input di DTO hanya `CODE ENTERED`,
bukan raw code. Journal dihapus setelah receipt terverifikasi atau rejection
terminal yang pasti. Lost ACK → lookup/retry key/body sama sebelum menerima kode
lain. Journal rusak memblokir redemption baru dan menampilkan popup, tidak dihapus
otomatis. Tidak pernah `cash += 5000` optimistik pada client.

## 6. Migrations, provisioning dan Docker

Tambahkan migration bernomor di repository backend, jalankan untuk dua DB:

| Tabel/kolom | Constraint/invariant |
| --- | --- |
| auth subjects: environment, role, realm_account_id | normalized user_id UNIQUE global; environment TEST/PRODUCTION; role TEST_OPERATOR hanya TEST; immutable routing |
| realm_clock singleton | revision>0; virtual_anchor_ms, real_anchor_ms, active_operation_key, fencing_token; hanya worker TEST memiliki writer |
| dev_clock_operations | key UUID UNIQUE; owner_account FK; action enum; request_hash BINARY32; expected_revision; target/time/checkpoint/final_revision/state/error; real created/lease/finished times |
| promotion_batches | id; environment atau DB realm invariant; label; currency NX_CASH; amount CHECK=5000; active_from/expiry domain timestamps; status; minted_count; real audit timestamps |
| promotion_codes | id; batch FK; hash_key_id; code_hmac BINARY32 UNIQUE; state ISSUED/REDEEMED/REVOKED; no plaintext code |
| promotion_redemptions | id; code_id UNIQUE FK; account FK; amount/currency immutable; ledger_id UNIQUE FK; credited_wallet_version; original wallet snapshot; timestamps |
| promotion_operations | account+key UNIQUE; request_hash BINARY32; state/outcome; redemption FK; durable response snapshot; real timestamps |
| wallet_ledger | UNIQUE source_type+source_id (CDK:redemption_id); currency/check/overflow rules existing; no dev transfer source |
| outbox/audit | realm/actor/action/operation IDs, no raw CDK/PIN/token; unique domain event |

Gunakan InnoDB, integer BIGINT untuk timestamp/cash, bounded enum/check/FK dan
prepared statements; schema nyata harus menyertakan indeks owner+state, code/batch,
job lease/pending. Tambahkan migration legacy subjects ke PRODUCTION, reserve DEV
name sebelum membuka registration, lalu provision DEV account TEST secara atomik
dengan starter nyata catalog OVR60an dan initial5000 sekali. Jangan membuat akun
DEV melalui public endpoint atau mengubah QA production yang sudah ada diam-diam.

Mint CLI/operator membaca HMAC key dari Docker secret, domain-separate dengan
environment+hash_key_id; simpan hanya keyed digest, bukan raw/unkeyed hash dari
kode pendek. Export kode sekali ke file privat inventory fulfillment; audit hanya
batch/count/operator. Key rotation mempertahankan key lama untuk kode belum habis.
Hindari plaintext code di SQL logs, request tracing, APM dan analytics. Tidak ada
public mint API. Penjualan/fulfillment kode dilakukan di luar client.

Compose: Go API/router, production worker, TEST worker dan **satu MySQL** tetap
dalam budget2GB. Environment/secrets terpisah: auth DSN, production DSN, TEST DSN,
production/TEST code HMAC keys dan reserved DEV User ID. Jangan meletakkan secret
di image/MD/repo/command line yang tercatat. Queue/cache/job namespace terpisah;
lease/budget TEST lebih kecil, tidak memblokir job produksi. Clock TEST tidak
mempunyai route untuk mengubah production scheduler. Uji koneksi worker TEST
menulis production DB harus ditolak oleh grants, bukan sekadar if-code.
Migration/provision/mint CLI adalah operator tools, tidak dipanggil NRO.

## 7. Acceptance sebelum enable capability

1. Login akun DEV dengan PIN benar otomatis TEST, login biasa PRODUCTION;
   wrong PIN/unknown ID generic; public register reserved ID gagal; header/body
   is_dev/TEST dengan token biasa tidak memberi clock scope. Refresh menjaga realm.
2. IDs akun/fixture sama di dua realm tidak saling terbaca. TEST clock/cash/pack/
   result/reward/RP/honours/logs tidak mengubah satu row/blob production. Buktikan
   DB grants dan ledger snapshots sebelum/sesudah, termasuk worker restart.
3. Switch login DEV → Join Senin → prep → Rabu LIVE/watch/touchline → ended →
   Join Kamis → prep → Sabtu → Sunday payouts → Monday berikutnya. Dua viewer pada
   virtual at_ms yang sama menerima frame/event/hash sama. Tidak ada streaming video.
4. Uji NEXT_MILESTONE/FINISH_WEEK, CAS race, dua key, same-key replay setelah
   revision naik, lost ACK, restart setelah tiap checkpoint/COMMIT, timeout polling,
   FAILED checkpoint; satu bonus/fixture/seal/payout saja. H1/2/3 BOT dan H0 empty.
5. Auth expiry/throttle/worker lease tetap real-time meski TEST maju7/14hari;
   publication/spoiler/ranking domain mengikuti virtual time. Production tetap nyata.
6. Mint TEST/production CDK terpisah; fresh credit tepat5000; same code+same/new
   key+same account tidak double; dua akun serentak hanya satu pemenang; code
   unavailable/expired/not-active/Unicode/overlength tidak credit. Berbeda CDK boleh
   credit ke akun sama. Wallet/ledger/operation sama setelah crash dan refresh.
7. Lost CDK ACK sebelum/sesudah commit, reboot Switch, lookup404 lalu replay exact
   key/body, malformed/wrong-owner/wrong-amount receipt, SD write failure/corrupt
   journal. Client tidak mengubah wallet tanpa receipt/bootstrap terverifikasi.
8. Uji kode aktif di NRO versi online yang masih diterima sebelum next update;
   version/catalog gate tetap normal untuk gameplay. Tidak menyalin code/token
   ke review publik. Log/artifact acceptance cukup ID request/receipt dan saldo.
9. OpenAPI typed schemas untuk seluruh auth context/capabilities/meta, empat route
   baru, success/error enums/nullable/check bounds; Go contract tests + MySQL race/
   rollback tests dan Switch hardware acceptance. Host mocks bukan bukti deploy.

## 8. Status source v106

Implementasi client: auto mode dari context login/refresh/bootstrap, TEST-only
request guard, header assertion, sessionv2 realm-bound (v1 perlu login ulang),
TEST payment journal berbeda dari production, clock/promo durable journals,
clock confirmation/loading/poll/recovery, cache invalidation/bootstrap, Shop
promotion input/receipt/popup dan minimum4 guide. DEV offline tidak diubah.
24 tes controller async host lulus, mencakup14 skenario baru. SDK syntax check
untuk provider, HTTP, dispatch dan UE4 UI/input lolos. Tidak ada akun DEV
dibuat, CDK di-mint, clock server digeser, atau build/NRO hardware yang diuji
oleh penulisan dokumen ini. Integrasi nyata menunggu deploy kontrak di atas.
