# Custom Playlist: native audio contract, v121

This investigation explains a confirmed v120 gain error and the native menu
audio route. It does not establish the cause of every reported Switch stall,
or claim a hardware playback pass.

## Evidence boundary

- Exact owned `dist/pes21_nx/libUE4.so`, SHA-256
  `a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
- Bounded reads from `Expansion/dt500_mobile_all.cpk` inside the owned patch
  OBB. The active `cpk_snd` ACF, both menu ACBs, and playlist XML match those
  source bytes exactly. No audio recordings were extracted.
- Native providers were unavailable in REA on this host. Findings use scoped
  ELF inspection, Capstone, and exact ARM64 instructions executed in Unicorn.
  The instruction oracle uses synthetic category memory and substitutes name
  lookup, engine lock/unlock, and notification endpoints. It is not a live
  game, mixer, or timing test.

## Confirmed category semantics

`criAtomExCategory_MuteByName` changes the category volume parameter to
`0.00001525` (approximately -96 dB), preserving the requested volume for
restoration. `GetVolumeByName` reads the attenuated volume while muted.
Consequently, v120's post-mute sampling almost silenced the custom playlist.
Its claim that category mute preserves the value returned by the getter was
incorrect. Capture the custom gain before acquiring the native mute.

The bounded instruction oracle produced these results:

| Operation | Getter volume | Mute flag | Saved restore volume | Cumulative lock pairs |
| --- | ---: | ---: | ---: | ---: |
| Initial category | 0.8 | 0 | 0.8 | 0 |
| Mute | 0.00001525 | 1 | 0.8 | 1 |
| Repeat same mute | 0.00001525 | 1 | 0.8 | 1 |
| Set volume to 0.35 while muted | 0.00001525 | 1 | 0.35 | 1 |
| Unmute | 0.35 | 0 | 0.35 | 2 |

Both getters perform zero engine lock operations. A mute state change takes
the CRI engine lock synchronously; setting the already-current mute state does
not. Normal category volume setters respect mute, update the saved volume,
and cannot make this category audible while its mute flag remains set.
Repeated getters therefore are not evidence of per-frame CRI lock contention.

`MusicManager::m_IsInitialized` is insufficient readiness evidence: its Init
only establishes the manager mutex/timer. `criAtomEx_IsAcfRegistered(0)` is the
quiet ACF readiness check. With ACF absent, the three unguarded category calls
(query mute, mute, query volume) produced three native notifications. The
readiness guard produced zero category calls, notifications, and lock calls.
A missing category name with ACF present returned zero/false silently.

`TitlePlaybackInterface::Update` may unmute menu and stadium categories after
native playback-control reacquisition. It is not an unconditional per-frame
unmute. Bound restoration checks and reacquisition attempts rather than
repeating an unrestricted retry from every pad update.

## Actual menu route

Both `MusicManager::Update` and `playlist::Player::Update` reach
`sound::sys::Interface::PlayBgm`, then `KS::CInfBase::Play`. This is the native
CRI path. The owned ELF has no dynamic `mpg123` symbol; the wrapper's generic
mpg123 exports do not establish an alternate native menu music path.

The native ACF contains these categories:

| Category | Native ID | ACF table index |
| --- | ---: | ---: |
| `DefVol_Menu_Music` | 60 | 42 |
| `OptVol_Menu_Music` | 351 | 98 |

All 25 songs in the Menu playlist reference both categories in their ACB
sequence commands and send to BUS2. The tutorial menu cue also references
both categories. Thus `OptVol_Menu_Music` is supported by the actual active
assets, not inferred solely from a symbol name.

The native `Interface::SetBgmMute(bool)` uses the snapshot
`BUS2_MenuBGMMuteON` with a 500 ms transition. That snapshot reduces BUS2 from
0.7 to zero, but it is a full nine-bus snapshot applied to every rack; restoring
with a null snapshot can displace another native Pause/Entrance/Highlight
snapshot. Category ownership is more composable here. Native `IsBgmMuting`
is an Android stub that returns false, so it cannot verify this snapshot.

| Owned metadata | Bytes | SHA-256 |
| --- | ---: | --- |
| `PES2021.acf` | 21664 | `ea09e8def07cf3954c1e1baf48fccae11fc2f61a89dbfe219ccdd8c17670901a` |
| `BGM_AM.acb` | 6880 | `847897c2750149f33cbddb05175ba10b697f06d851c00168ae3621e995ec94f1` |
| `BGM_P2P_AM.acb` | 9664 | `2d8c3a2495c2820eb45bafa8897e33cd0dc2de0f108a3d58e04bf936b65311f6` |
| `Playlist.xml` | 6046 | `53ab6f5c5703cb5e26c0fbcf54584a2bd70be12ba9b0c05730f5f7433b6399bd` |

## Integration contract

Native calls belong to the game owner, with rate-limited observation and
transition-driven mute ownership. The existing pad hook executes before
pad-ID filtering, so it can be entered more than once per frame. The adapter
must independently bound its work. Static inspection did not identify a
lock-order cycle at this call site; it also cannot prove Switch scheduling
or filesystem latency.

Preserve native SFX/commentary and let native setters retain their restoration
semantics. Restore only mute state acquired by the wrapper, stop custom PCM
before match playback, and provide native fallback if readiness or acquisition
fails. Cache pre-mute gain; never use the muted getter to refresh custom gain.
If live menu-volume changes must affect custom audio, consume the requested
setting change rather than reading the attenuated category again.

The release regression oracle should model an attenuating mute, readiness
failure, native unmute/reinitialization, repeated pad calls, starvation,
ON/OFF transitions, and match entry. Hardware verification still needs to
check audible exclusivity, responsive navigation, native SFX, and match audio.

## ABI and body guards

Addresses are ELF-relative and hashes are FNV-1a 64 over the complete body.

| API and ABI | Address | Bytes | FNV-1a 64 |
| --- | --- | ---: | --- |
| `int criAtomEx_IsAcfRegistered(int notify)` | `0x750f854` | `0x44` | `0x077e2ca84ca368ef` |
| `void criAtomExCategory_MuteByName(const char *, int)` | `0x750cbfc` | `0x50` | `0x08af5c32184f8165` |
| `int criAtomExCategory_IsMutedByName(const char *)` | `0x750cc4c` | `0x98` | `0xc3163b9e72ec8220` |
| `float criAtomExCategory_GetVolumeByName(const char *)` | `0x750c4a4` | `0xac` | `0xc7c7a9da2ced689d` |

No production native code was changed by this investigation. Raw disassembly
and extracted metadata were removed after these findings were recorded.
