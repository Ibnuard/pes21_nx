# Custom Playlist playback correction, v121

The v120 hardware report describes native BGM continuing, audio stuttering,
and an almost unresponsive Switch after enabling a user MP3. The earlier host
tests did not model the native mute implementation. v121 corrects the proven
volume/readiness bugs and bounds decoder work and recovery. The complete
device stall has not been reproduced on a physical Switch here.

## Findings and changes

The [native instruction audit](CUSTOM_PLAYLIST_NATIVE_V121.md) proved that
muting `OptVol_Menu_Music` changes the getter's result to approximately -96 dB.
v120 sampled that attenuated value for custom PCM. v121 captures the music
gain before muting and retains it for that menu playback interval. The same
audit verified that all 25 native menu songs use this category. SFX and match
audio retain their existing mixer routes.

The adapter now checks registered CRI audio configuration directly. The
MusicManager initialization flag was not sufficient, and could also prevent
restoring a mute during manager teardown. Four complete native function
bodies are checked before binding their audited ABIs. Missing symbols or
changed bodies leave native audio available.

Native state observations run at most every 500 ms, independently of the
number of pad callbacks. Volume getters are used only before acquiring mute.
An unacknowledged mute falls back once; it cannot retry every frame. Repeated
native ownership changes allow at most three acquisitions during a menu
stay, then retain native music until OFF/ON. Normal menu/match transitions
start a new ownership interval and do not exhaust this limit.

A brief empty PCM buffer closes custom output while retaining the music
mute for up to 750 ms. Refilled PCM resumes after its normal prefill threshold.
Persistent starvation restores native music once and latches fallback until
OFF/ON. OFF and leaving menus restore native music immediately. One bounded
fault record goes into the existing `scene-runtime.log`; there is no per-frame
or audio-callback file logging.

The decoder previously performed an entire two-second prefill without a
scheduling point (55 consecutive decoder calls in the synthetic regression,
including format negotiation and track boundaries). It now sleeps 1 ms after
at most two decoder calls. The 200 ms prefill, two-second ring, worker priority,
core affinity and existing AudioOut path remain unchanged. A full ring with
no consumer stops decoding and sleeps; invalid/no-progress streams stop after
bounded attempts. Native SDK inspection ruled out failed nanosleep, implicit
core pinning, or a high-priority worker as established causes.

These changes address concrete defects and prevent repeated recovery work.
The native getter functions do not acquire the CRI engine lock, so per-frame
getter lock contention is not asserted as the cause of the reported stall.
Live native volume changes during an acquired mute are retained by CRI for
restoration; custom gain is recaptured at the next menu ownership interval.

## Recovery and delivery

If v120 cannot be navigated, edit `switch/pes21_nx/pes21_nx.cfg` on the SD card
using a PC and set `custom_playlist 0` before the next launch. No save reset
is needed. This update changes the client NRO only; it needs no backend
deployment, database migration, roster update or replacement music assets.

The v121 build uses the unchanged v120 paired inputs, runtime pair
`e861c583ec78e9ae` and dummy patch OBB of 53,248 bytes. No songs are bundled.
Place user MP3s directly in `switch/pes21_nx/playlist/`, enable in initial
Settings, and use OFF/ON to rescan or clear a session fallback.

## Verification

Executable regressions cover the actual production adapter, realistic native
mute attenuation, ACF absence/teardown, bounded pad calls, rejected mute,
native overrides, brief/prolonged starvation, normal menu/match transitions,
OFF/ON, ABI rejection, worker scheduling and no-progress decoding. The
native oracle executes exact ARM64 instructions with synthetic category data
and stubbed lookup/lock endpoints; it is not a live mixer or hardware test.

Final test, real MP3, source/input-pin, build and package evidence is retained
under ignored `local-debug/manager-v121/`. Physical Switch acceptance remains
required for responsive navigation, audible playlist/native exclusivity,
native effects, and stopping custom BGM during matches.

The focused Windows batch passed 42 tests and 335 subtests; one Linux-library
integration was unavailable there. The additional production adapter/worker
test passed separately on Linux with a generated 44.1 kHz mono MP3, paced
48 kHz stereo output, audible pre-mute gain, zero empty blocks, and menu/OFF
restoration. A separate three-second parallel-decoder host measurement had
zero underruns; its timings are not Switch performance measurements.

The release ARM64 build completed and the public-tree audit checked 1,577
files. The delivery verifier checks all 249 pinned source/build files, all
nine unchanged paired inputs, all four native API bodies, ELF/NRO load
segments, the embedded icon, and every ZIP entry.

Verified release NRO: 86,848,415 bytes, SHA-256
`cea7ef5090ff70052afcbda61a05eff4306c7eb1ebce17914643cff74b557add`,
build ID `037b9955a8b176bb2dcb58d5a074233a07879b36`.
`FootballNX27-v121-PLAYLIST-FIX-SIAP-COPY.zip` is 46,166,891 bytes, SHA-256
`5bc3b5d46c80dd0e913ed9cc4d8cf39c21e4d198d340971148401285b21b265d`.
The active runtime was not overwritten during this build.
