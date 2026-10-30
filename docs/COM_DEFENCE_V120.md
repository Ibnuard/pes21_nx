# One-player COM cursor ownership v120

The one-player adapter now finalizes every AWAY cursor as CPU-owned after the
native tmpdb cursor loader returns. It writes pad `-1` and the native CPU flag,
preserving HOME cursors, player selection, support settings, and AI difficulty.
The accepted two-controller path remains separate.

## Confirmed ownership gap

The earlier `pes_cursor_set_pad_no()` correction only set AWAY's pad to `-1`.
That does not establish CPU ownership in the supported native runtime:

- `CursorInfo::IsUserPlayTeam` accepts either a physical pad or the alternate
  ownership byte at cursor offset `0x03`, unless CPU flag `0x0d` is set.
- `CursorInfo::IsUserControlTeam` checks the selected player, coach flag and
  CPU flag. It does not check the physical pad number.
- `CheckControl::InitByCursorInfo` uses `IsUserPlayTeam` for both teams.
- The existing finalization callback handled only two-player matches, leaving
  the one-player path without a final CPU-ownership check.

A mobile or retained human AWAY cursor could therefore still be classified as
user-controlled while the one-player input router deliberately supplies it no
input. This is a concrete ownership defect consistent with a selected defender
waiting for input. It does not establish that every instance of passive COM
defending has this cause.

## Evidence and validation

Read-only inspection used the user's local ARM64 `libUE4.so`, SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
REA reported no configured Ghidra or IDA provider; the observations below come
from ELF/Capstone inspection and bounded Unicorn execution, not REA decompilation
or a Switch trace.

| Native routine | Address | Observed body size |
| --- | --- | --- |
| `CursorInfo::IsUserPlayTeam` | `0x06800d94` | 100 bytes |
| `CursorInfo::IsUserControlTeam` | `0x06800b88` | 156 bytes |
| `CheckControl::InitByCursorInfo` | `0x07bea640` | 72 bytes |
| `CursorData::ChangeCpu` | `0x067feb64` | 80 bytes |
| `MatchListener::SetCursorInfoFromTmpdb` | `0x07be1d64` | 4560 bytes |

The host C regression executes the same callback used by the NRO. It covers
mobile ownership with no pad, stale AWAY pad 0 and pad 1, repeated finalization,
two-player to one-player and back, and an inactive adapter. Byte comparisons
verify that unrelated cursor fields and HOME records stay unchanged.
The host suite passed on Windows and with Linux UBSan. The Linux run used a
task-local temporary directory after the first compiler invocation lost its
temporary assembly file; no sanitizer failure occurred.

An additional local oracle ran the first three native routines above in an
isolated ARM64 emulator against the C callback's before/after cursor records.
All three reproduced ownership states changed from HOME/AWAY `[1, 1]` to
`[1, 0]`; HOME stayed human and AWAY became CPU. The control predicate used its
stored cursor-change override, avoiding its external support-setting call.
Only these bounded functions were emulated; the game was not launched.
The compact oracle result remains under ignored `local-debug/com-defence-v120/`;
temporary disassembly and executables were removed after verification.

Run the permanent regression with:

```powershell
python -m pytest tests/test_native_pad_routing.py -q
```

Switch acceptance remains necessary: test Legend versus COM across possession
changes, halftime and rematch, then two-player followed by one-player. No AI
aggression, reaction speed, tactics, player attributes or difficulty constants
were changed.
