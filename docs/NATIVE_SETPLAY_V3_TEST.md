# Native Setplay V3 - goal-kick device test

Kandidat aktif untuk eksperimen full-native set-play berada di
`local-debug/native-setplay-v3-20260901/`. Kandidat ini terpisah dari dan tidak
menimpa Native Mapping Baseline V1.

Salin hanya `install/pes21_nx.nro` ke
`sdmc:/switch/pes21_nx/pes21_nx.nro`. Pitch visual-v14, OBB, roster, dan aset
lain tidak berubah. Instruksi pengujian lengkap serta arti telemetry ada di
`local-debug/native-setplay-v3-20260901/README.md`.

Scope iterasi ini sengaja hanya goal kick: LS aim, L support, B short pass,
A long pass, dan Y shoot menggunakan ThinkUnit native; X belum dipetakan.
Corner, throw-in, free kick, power-gauge presentation, dan controller kedua
tetap menjadi iterasi berikut setelah hasil perangkat goal kick diketahui.

Status: **host/ABI validated, Switch test pending**.
