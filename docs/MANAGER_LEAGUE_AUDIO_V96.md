# Manager League native PCM audio candidate v96

The v95 device journal admits each request but then returns `0x80000010`
(retired handle), with no play position, by the first 100 ms observation. This
includes the 21 second supporter bed and multi-second speech, not only the 77 ms
pass contact that may legitimately have ended by 100 ms. The listener reports
ordinary menu music, with no supporter/contact/commentator audio. Thus request
admission did not establish native voice playback; changing the BUS8 route in
v95 did not resolve it. The exact decoder or voice-allocation cause remains
unconfirmed by that journal.

REA's selected target is the compatible native ELF
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
Its native ARM64 ELF analysis provider is unavailable on this Windows host.
No additional analysis engine was installed. The supporting native observations
below come from bounded original-ELF Unicorn execution and source tooling,
not from a REA decompilation or an emulated audio device.

The v96 candidate uses an independent native WAVE pool and PCM16 memory bank.
`stage_manager_pcm_audio.py` accepts only the sealed v94 bank and its original
individual semantic review. It decodes the 13 reviewed HCA recordings at their
original 48 kHz, removes the declared leading encoder delay, and retains exactly
the ACB's native `NumSamples` window. Mono channels are duplicated into stereo;
no resampling, new speech, source-file modification, lossy encode, normalization
or compression is performed. Existing conservative cue gains are applied once
before PCM16 quantization, so decoded HCA overshoot cannot clip at conversion.
The cue's runtime gain is unity. Private reports retain each source recording,
decoded and quantized PCM hash, sample counts, semantic transcript and peak.

The original native WAVE analyzer, decoder constructor and full decoder are
executed for all 13 PCM recordings. The resulting samples and channel order must
roundtrip exactly to every staged PCM16 sample. The original native WavePlayer
configuration parser and pool selector are also executed, showing a distinct
WAVE format mask `0x20` beside existing ADX/HCA masks `0x02/0x08`. These probes do
not allocate a platform audio voice or run an audio device.

The adapter checks eight complete native method bodies and RVAs before exposing
call targets. The two additional methods are the native WAVE worksize calculator
and allocator already ABI-checked for the historical trophy PCM experiment.
One process-lifetime pool has six voices: three owned roles (bed, commentary,
effect) plus bounded outgoing 100 ms fade headroom. Its configuration is identifier 0,
stereo 48 kHz, nonstreaming, renderer 2 (the native software/ASR mixer), decode
latency 0. Caller-owned work is capped at 2 MiB. A rejected size or allocation is
terminal for the session. Successfully registered backing and mounted source
data remain alive to process exit; view exit only stops owned handles.

The bank is bounded at 16 MiB. Native schema, ACF identity, cue/sequence/track/synth
graph and v95's explicit MasterOut 0 / BUS8 = 1 sends are retained. Existing trophy and
ADX/HCA pools, global gains, menu playlist and unrelated sound configuration are
unchanged. Manager no longer admits any plaintext-HCA decoder exception. The
supporter bed is a finite 21 second WAVE cue which the owner cycles at its declared
endpoint, avoiding assumptions about a RIFF loop parser or borrowed HCA loop
metadata. A small boundary gap remains possible.

Live event deduplication, no historical speech on late join/seek, goal priority,
stale publication shutdown and replay supporter/contact-only policy remain.
The bounded owner journal observes short contacts at 0 / 20 / 100 ms and longer roles
at 0 / 100 / 1000 ms. Each entry identifies whether the clip should already have ended;
an expired short contact is not labelled a failed start. The journal retains
one previous session and is capped at 64 KiB.

Staged asset: `Audio/manager-league-pcm-v96.acb`, 13,909,856 bytes, SHA-256
`ffc8f544530e49a54de2558630ba584c96ff9d5016e2969c4c2d77befe4b7b50`,
FNV-1a64 `d2e4f5e7bc2dd111`. Payloads and proof receipts remain ignored under
`local-debug/manager-review-v96/audio/pcm-01/`; historical v94/v95 banks remain
sealed. This is a host-verified candidate. Audibility, balance with the existing
menu music and hardware voice allocation still require Switch listening and
the dedicated `manager-audio-runtime.log` from that test.
