# Trophy music level and PCM quality (v90)

The user confirms that v89 music plays on Switch, but reports excessive volume
and crackle confined to the trophy BGM. Crowd and commentary remain clean.
The supplied recording, its desktop ADX decode and its original native ADX
decode contain no clipped or non-finite samples. The source is −13.77 dBFS RMS,
roughly 11 dB hotter than the earlier FL26 reference. Native ADX output is
−13.73 dBFS RMS with peak 0.938. The extra 4-bit ADX encode has 35.20 dB measured
signal-to-error ratio against the supplied clip. The native and independent
ADX decoders correlate at 0.9999971; the evidence does not show broken channel
framing or a gross native decoding error.

The v90 cue uses PCM16 WAVE, eliminating that additional lossy encode. Only
this cue's staged samples receive −12 dB attenuation (linear 0.2511886432),
before any playback request. The original supplied file remains read-only.
All 688,128 stereo samples at 44.1 kHz are retained, without normalization,
compression, trimming, downmixing or resampling. Rounding to PCM16 introduces
at most half a least significant bit. Native output peak is 0.2359009 and RMS
is −25.7669 dBFS. Independent decoding preserves the staged PCM exactly. The
original native WAVE analyzer/create/decode functions reproduce every PCM16
sample and channel exactly, with zero floating sample error, clipping or
non-finite samples. This removes ADX quantization rather than only hiding it
with lower gain.

The original ACB waveform reader maps EncodeType 20 to WAVE format 5. However,
ordinary native StandardPlayerPool factories attach only ADX and HCA decoders;
a working WAVE decoder alone does not establish playback admission. The
adapter therefore uses the original WaveVoicePool CalculateWorkSize/Allocate
functions to register one voice, two channels, maximum 44.1 kHz, no streaming,
native software/ASR renderer 2 and default decode latency. It uses identifier
0, matching an unspecified native cue pool, with native format mask `0x20`.
Executing the original config parser and pool selector proves WAVE requests
select that pool while ADX/HCA format masks continue selecting their existing
pool. No existing pool or renderer configuration is changed, and no second
audio device is opened.

Actual work size is obtained in the live native audio context. Non-positive
sizes or sizes over 1 MiB are refused. The caller supplies the backing to the
native allocator and retains it after successful pool registration for process
lifetime. The mounted bank follows the same lifetime rule. Teardown stops only
the ceremony handle with the existing fade; it cannot free backing beneath a
native callback. Allocation failure leaves the ceremony running without music
and is not repeatedly retried. A host with no active native ASR platform
interface cannot establish a genuine live allocation size or voice playback;
the device log records that size when allocation succeeds.

The exact v89 native sequence/category/bus route is retained. Its bus commands
send zero to `MasterOut` and one to `BUS8`, rather than two full-volume parallel
sends. The original command interpreter reads the 16-bit level and divides it
by 10,000. No global category gain, playlist, mixer callback or commentary path
is modified. Existing bounded status/position observations and retired-handle
stop behavior remain in place. All nine native binding bodies remain checked.

The bank `Audio/trophy-user-pcm-v90.acb` is 2,758,200 bytes, SHA-256
`2d7512a25c6c2289db0f2005771a9fd7fbbf319701a52d2686c84d734600f837`.
The 4 MiB bank cap accommodates this measured full recording; it does not permit
unbounded input. Staging/proofs/tests remain ignored under
`local-debug/presentation-v90/music-01/`; v89 banks and evidence remain sealed.

PCM and added headroom address measured encoding loss and excess level.
No device mix recording or underrun evidence was supplied, so downstream mix
clipping or callback underruns cannot be assigned as the confirmed cause of
the reported crackle. Clean, balanced v90 output still requires a Switch test;
host decoding and pool-selection proofs do not establish device audio quality.
