# Corner startup followup v70

The v69 candidate crashed before entering the game. The supplied journal
ended at `referee presentation: v61 offside fixed-demo layout admitted`,
before corner admission and selected-roster commentary installation.

`main` installs hooks before `so_finalize` maps the game's runtime alias.
The corner installer mistakenly hashed the future RX address returned by
`so_try_find_addr_rx`. That read can fault even though the ELF already exists
in its writable backing allocation. The earlier host adapter fixture returned
missing symbols during installation, so it tested only optional fallback.

The fix keeps the two address roles separate. Every opcode read and table
range check uses bounded `load_base` bytes. The executable runtime aliases
remain stored for future native calls and relocated vptr comparisons. The
existing writable vtable helper applies only the admitted defence slot.
Missing, out-of-range or mismatched input disables this optional feature
before patching it. No native AI, geometry, controller selection or accepted
asset payload changes are included.

`test_corner_startup_v70.py` compiles the actual installer. Its local fixture
extracts the owned seven bounded opcode bodies into a temporary RW allocation
and reserves the separate RX allocation with no-access protection. The v69
implementation fails the successful-install case. The corrected installer
passes that case plus missing/corrupt/range/table faults, preserves runtime
call/vptr identities and alters only the exact writable vtable slot. Owned
opcode bytes remain ignored temporary data; missing local ELF fixtures skip.

The replacement release retains the reviewed helper art, bench/rematch
boundary, referee changes and byte-identical v68-r2 `FootballNX.assets`.
It uses an isolated production build with serial compilation/LTO and a v70
journal marker. The ready-copy folder includes the NRO and unchanged asset
archive for convenience; an installation already carrying the v69 archive
needs only the NRO replaced. Host tests/build/hash/ZIP do not establish Switch
boot or gameplay acceptance. The next device journal should pass the new
`v70 bounded RW guards passed` message before commentary installation.
