# Custom trophy music level (v99)

The user reports that the v97 recording is clean but still slightly quieter
than commentary. v99 raises only that custom recording by another 3 dB. Its
baked attenuation is now -3 dB relative to the original supplied recording,
compared with -6 dB in v97 and -12 dB in v94. Native categories, bus sends,
existing HCA voice pool, ceremony ownership, fades and stops remain unchanged.
No global music or commentary volume is changed.

`tools/stage_trophy_gain_music.py` defaults to the v99 recipe and retains the
sealed v97 recipe for historical checks. It verifies the original MP3
(`3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff`),
its full decoded PCM, the sealed v97 bank and the previously reviewed encoder.
It attenuates that original PCM once, then encodes a new highest-quality,
non-looping plaintext HCA. The earlier lossy HCA is decoded only to measure
the level difference, and is never used as encoder input. There is no
normalization, compression, resampling, downmixing or trimming. The tool
requires a fresh ignored `local-debug` directory and cannot install a bank
into the active runtime or overwrite an earlier stage.

The recording still contains all 688,128 stereo frames at 44.1 kHz. Independent
FFmpeg decoding measures a 2.999866 dB RMS increase over v97: RMS is now
-16.766819 dBFS, peak is 0.665239, and recording peak headroom is 3.540449 dB.
There are zero clipped or non-finite samples. Signal-to-error ratio against
the gained original PCM is 38.609364 dB. The encoder/FFmpeg global polarity
convention is accounted for only in quality comparison, without changing
playback samples. Recording headroom alone does not prove final mixed audio
headroom or a preferred balance on Switch.

The detached bank is `Audio/trophy-user-hca-v99.acb`, 695,036 bytes, SHA-256
`f83690edd7c5d2c124277051f0cdaf69a28516e2f6639557abf64fecdb429ec8`,
FNV64 `4bdd1b18cd509fbc`. Its cue is `FNX_TROPHY_USER_HCA_V99`. Every native
graph, waveform, category, command, string and ACF table remains byte-identical
to the sealed v97 bank. The owned 96-byte HCA header fingerprint is unchanged,
because codec settings and frame count remain unchanged. The complete new
bank is still fingerprinted before runtime ownership is published.

The exact original native HCA reader accepts the unchanged 96-byte header and
all 673 plaintext packets. That bounded probe does not execute PCM synthesis,
the mixer or an audio device. Its native-library fingerprint remains the
previously reviewed compatible Mobile library; no new analysis engine or
native playback installation is required.

The focused v88, v89, v90, v94, v97 and v99 suite passes 27 tests. It rechecks
the new independent full decode and relative level, historical banks, current
bank mount caching, native header/packet admission, gain rounding and channel
count, original ABI checks and ceremony-owned stop behavior. Private bank and proof receipts remain under
`local-debug/manager-review-v99/trophy-audio/stage-01/`. No game audio, native
binaries or runtime traces belong in the public tree. The staged bank is not
installed, no NRO build is performed by this workflow, and device listening
remains required before calling the new balance accepted.
