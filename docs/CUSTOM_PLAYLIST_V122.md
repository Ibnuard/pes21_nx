# Custom Playlist input correction, v122

The reported v121 build played broken audio for one to two seconds, then
restored native music. Both supplied scene logs identify build
`037b9955a8b176bb2dcb58d5a074233a07879b36` and the same 750 ms PCM-readiness
fallback. The log alone did not distinguish a decoder failure from an empty
ring or stale heartbeat.

## Reproduced cause

The supplied file has a `.mp3` suffix but contains an MP4 `ftyp dash` container
with AAC-LC, 44.1 kHz stereo audio. FFprobe and a complete FFmpeg decode agree
on a duration of 213.09 seconds. Input SHA-256:
`64ef5179f7c119383836b56506b80c963ebe7bd1f6dd9faf41d0afe35d31a07e`.
The original file remains untouched; no recording is committed or bundled in
the client update.

With the production mpg123 parameters, the host decoder finds false MPEG
sync words in this AAC payload. It returns 197,396 bytes (1.028 seconds at the
configured PCM rate), reaches the signed-16 clipping limit, then returns an
error. Some reads take hundreds of milliseconds or more. This is not valid
decoding of the song and reproduces the mechanism behind the short distorted
output followed by starvation. Host measurements are not Switch timings.

v121 also regarded any decoded frames as evidence that a track was healthy,
even when its final result was an error. Such a file could reopen indefinitely.
The earlier generated-MP3 tests did not cover a mislabeled MP4/AAC input or a
decoder that emits partial audio before failing.

## Correction

- The worker reads only the first twelve bytes before creating a decoder.
  Recognizable MP4 boxes, Ogg, FLAC, RIFF, FORM, CAF and ADTS AAC are rejected
  before mpg123 can search them for MPEG sync words. This is a bounded
  signature guard, not a general validation guarantee for arbitrary corrupt
  MP3 files. Ordinary MPEG and ID3 inputs retain decoder handling.
- Failed open/format/decode/no-progress tracks are skipped for the remainder
  of the enabled session. Partial output no longer makes an errored track
  eligible for another loop. Healthy tracks still loop; OFF/ON rescans and
  permits another attempt after files have been corrected.
- The worker publishes format/decode notice bits. The owner writes each
  notice at most once per enabled generation into `scene-runtime.log`.
  Audio callbacks do no file logging; input warnings do not mute native BGM
  or stop valid tracks in a mixed folder.
- The existing playlist helper explains that changing AAC/M4A's extension
  does not convert it to MP3.

The native ownership adapter, pre-mute gain, ring size, prefill threshold,
decoder scheduling and 750 ms fallback policy retain their v121 behavior.
An independent audit of the installed SDK found a shared hardware-counter
clock and a one-buffer AudioOut release contract consistent with the existing
consumer. It did not establish a clock/TLS or requeue defect causing this
report, so those paths were not changed.

## Verification and installation

Focused executable tests cover rejected container signatures, MPEG/ID3
admission, a mixed folder, partial-output decoder errors, continued healthy
loops, native-buffer preservation, warning rate limits, and existing audio
ownership, generation, scheduling and menu tests. A concurrency test now
allows the documented nonblocking mixer to defer a buffer during lock
contention, then verifies the eventual samples.

`tests/test_custom_playlist_real_v122.py` optionally accepts private fixture
paths in `PESNX_PLAYLIST_WRONG_INPUT` and `PESNX_PLAYLIST_MP3_INPUT`. It uses the
actual production worker and adapter with host libmpg123 and mocked native
category calls. It verifies zero decoder calls and zero native mute calls for
the reported input, then paced 48 kHz playback of its converted MP3, followed
by native restoration on menu exit. It does not emulate Switch AudioOut.
The generated-tone v121 integration continues to check mono resampling,
pre-mute gain and OFF/ON ownership.

The separately provided conversion is real MP3, 48 kHz stereo, 192 kb/s, and
has passed a complete decode. Remove the mislabeled file from the SD playlist
and copy the converted MP3 there. Use OFF/ON to rescan. No save/config reset,
backend deployment or game-asset replacement is required.

The v122 client-only NRO uses the unchanged runtime pair `e861c583ec78e9ae`
and 53,248-byte dummy patch OBB. Build, source/input pins, focused tests,
private-input integration, ELF/NRO and ZIP verification are retained under
ignored `local-debug/manager-v122/` and `local-debug/custom-playlist-v122/`.
Physical Switch audio and responsiveness remain the hardware acceptance step.

The completed focused batch passed 57 tests and 335 subtests; one host-library
case is unavailable on Windows. Both real-libmpg123 integration bodies passed
on Linux: the supplied wrong-format file reached zero decoder/mute calls,
and its MP3 conversion played 188 paced blocks with zero short blocks and
zero fallback. The full MP3 decoder pass also reached the expected clean end
after 213.0895 seconds of PCM. The generated-tone test passed with no empty
blocks and retained menu/OFF/ON restoration. Its strict timing assertion failed
once while the release compilation ran concurrently; the instrumented
standalone rerun passed. These results are functional host checks, not a
Switch scheduling or load benchmark.

On 30 October 2026, the user reported successful playback on their Switch
after receiving v122 and the actual MP3 conversion. This confirms the reported
playlist case on that device; it is not a separate measurement of every
menu/match transition, file type or hardware configuration.
