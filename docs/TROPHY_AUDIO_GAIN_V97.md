# Custom trophy music level (v97)

This is the sealed historical v97 level. The next isolated adjustment is
documented in [TROPHY_AUDIO_GAIN_V99.md](TROPHY_AUDIO_GAIN_V99.md).

The user reports that the v94 custom trophy song is now clean on Switch, but
is too quiet beneath commentary. v97 raises only this recording by 6 dB: its
own baked attenuation changes from -12 dB to -6 dB. The native category, bus
sends, existing HCA pool, ceremony token, fade and stop ownership are unchanged.
There are no global music/category/commentary volume changes.

`tools/stage_trophy_gain_music.py` verifies the original supplied MP3, its full
decoded PCM against the v90 review fingerprint, the sealed v94 bank and the
previously reviewed encoder. It attenuates that original PCM once, then encodes
highest-quality non-looping plaintext HCA once. It does not amplify/re-encode
the old lossy HCA, normalize, compress, trim, downmix or resample. The original
file and all earlier banks remain exact. Only a new ignored `local-debug`
directory can be written; this tool cannot install a bank into an active
runtime or overwrite an earlier stage.

The entire 688,128-sample stereo 44.1 kHz recording is retained. Independent
FFmpeg decoding yields peak 0.476127, RMS -19.7667 dBFS, zero clipped or
non-finite samples and 38.6153 dB signal-to-error ratio. This is 6.0001 dB above
the v94 independently decoded RMS, with approximately 6.45 dB recording peak
headroom. The encoder/FFmpeg global polarity convention is accounted for only
in the quality comparison, without changing playback samples.

The new detached bank is `Audio/trophy-user-hca-v97.acb`, 694,988 bytes, SHA-256
`634355f8955691730f5e0955f93f19f6ed1da3a7ba6adae654d80f5b056112bd`,
FNV64 `d615c5e52ec7385b`. Its cue is `FNX_TROPHY_USER_HCA_V97`. Every native
graph, waveform, category, command, string and ACF table is byte-identical to
v94. The owned header fingerprint is unchanged because the codec settings and
frame count are unchanged; runtime admission still checks the entire new bank
before publishing ownership. Runtime journal gain values come directly from
the generated catalog and explicitly report that the gain is baked once.

The exact original native HCA header and packet reader accepts the header and
all 673 packets without modifying their bytes. This bounded existing native
probe stops before PCM synthesis and does not run the audio device or mixer.
The independent full PCM decode and this native parser proof are distinct;
neither establishes the final balance against commentary on Switch. Device
listening remains required before calling the new balance accepted.

The focused trophy tests (v88, v89, v90, v94 and v97) pass 23 tests. They cover
current bank integrity and mount caching, historical sealed banks, native
header/packet admission, gain rounding/headroom, unchanged routing, original
ABI checks and ceremony-owned stop behavior. Private staged audio and proof
receipts remain under `local-debug/manager-review-v97/trophy-audio/stage-01/`.
No game audio, native binaries or runtime traces belong in the public tree.
