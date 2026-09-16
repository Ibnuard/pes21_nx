# Native Setplay V4 - dual-stick device test

Kandidat V4 berada di
`local-debug/native-setplay-v4-20260901/` dan belum menggantikan Native Mapping
Baseline V1.

Salin hanya `install/pes21_nx.nro` ke
`sdmc:/switch/pes21_nx/pes21_nx.nro`. V4 memasukkan LS sebagai arah tendangan
dan RS sebagai input kamera native pada goal kick, corner, dan free kick.
Overlay memperlihatkan `LIVE LS/RS`, `LPOW/RPOW`, tombol, serta command
ThinkUnit agar hasil perangkat bisa dilokalisasi.

Instruksi dan arti telemetry lengkap:
`local-debug/native-setplay-v4-20260901/README.md`.

Status: **host/ABI validated; Switch test pending**. Throw-in dan power gauge
visual belum termasuk kandidat ini.
