# Manager League PCM output path v99

The user-supplied `manager-audio-runtime.log` from the v98 test contains two
records: the adapter was armed, then its private WAVE voice pool was rejected.
It never reached bank mounting or a commentary request. Ordinary menu BGM is
audible in that same view. This establishes a failure before playback and a
working existing output path; it does not identify the internal CRI allocation
limit or renderer failure. Increasing cue volume cannot repair that rejection.

The selected compatible native ELF is
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
REA opened and identified this target, but its native deep-analysis provider is
unavailable on this Windows host. The owned session was closed. Bounded original
ELF instruction inspection confirms separate pool worksize and player-creation
failure branches; it is shell evidence, not a REA decompilation or device run.
The reason for the device's CRI player-creation failure remains unknown.

Production now blends the previously reviewed PCM into the existing final
stereo 48 kHz PCM16 AudioOut buffer, after native resampling and before the same
`audoutAppendAudioOutBuffer` call. It creates no device, stream, native voice
pool, decoder exception, native category change or playlist operation. The
native menu and trophy audio path is unchanged outside the Manager watch view.

The asset is unchanged: `Audio/manager-league-pcm-v96.acb`, 13,909,856 bytes,
SHA-256 `ffc8f544530e49a54de2558630ba584c96ff9d5016e2969c4c2d77befe4b7b50`.
The owner verifies its complete size/FNV fingerprint and all thirteen bounded
RIFF PCM ranges before publishing its process-lifetime allocation. Generated
metadata contains only offsets/frame counts. `index_manager_pcm_audio.py`
requires the sealed SHA-256 and follows native `CueIndex`, because cue-name row
order is alphabetical and is not waveform order. Recording samples, baked gains,
semantic review, sample rate and channel order are unchanged. No new asset copy
or proprietary payload belongs in the public repository.

The existing event policy owns bed, effect and commentary roles. Three outgoing
100 ms fade tails allow six bounded PCM voices. The bed loops its original
21-second sample window; commentary and effects complete once. New voices have
a 10 ms attack. Pause, exit or a two-second stale publication fades owned audio
out within 100 ms. A callback timeout also reanchors the event cursor on return,
so an old event is not announced again. Live goal speech supersedes an obsolete
shot line, late joins/seeks do not replay past speech, and Replay retains only
bed/effects as before. Half-time/full-time speech remains unavailable; no
unreviewed phrase is substituted.

While the visible, unpaused watch view is current, the final native BGM buffer
smoothly approaches 20% gain to make the reviewed commentary audible. This is
local output blending, not a persisted or global game-volume change. Native gain
returns exactly to unity on exit, pause or stale publication. Saturating integer
addition prevents wraparound. With no owned voices and unity native gain, the
buffer is returned untouched, sample for sample.

Publication and mixer ownership use short try-locks. Neither the game owner nor
the output callback spins. The callback performs bounded math over at most six
voices, without file I/O, logging, memory allocation or native mixer calls.
Loading/hashing and bounded journal writes happen on the game owner outside the
PCM lock. Contention skips one output block or one owner tick; it cannot retain a
lock while accessing storage. The dedicated journal now reports source frames
actually consumed and output-buffer frame/nonzero/peak counters. These counters
describe samples prepared before AudioOut submission, not verified speaker
audibility.

`test_manager_league_audio_v99.py` checks all thirteen real recordings against
their independent per-recording PCM SHA-256, normal attack-envelope math,
clipping, capacity, damaged/missing source behavior, native unity restoration,
event deduplication, goal priority, stale restart, and owner/output contention.
It compiles the production `aaudio_fill_output_buffer` function with a stubbed
device sink to establish that the blend occurs after native resampling and
before existing AudioOut submission. This host proof does not execute a Switch
audio device. Native v96 pool/decoder experiments remain isolated in the
test-only `fixtures/manager_league_native_audio_v96.inc`; production never
includes that rejected candidate. Hardware listening and the new dedicated
journal are still required to confirm audibility and mix balance on Switch.
