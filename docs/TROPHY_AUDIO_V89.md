# Trophy music: custom recording and native playback state (v89)

The user replaced the FL26 trial with a supplied local recording. Although its
filename ends in `.mp3`, the supplied file contains AAC-LC in an MP4 container:
253,244 bytes, SHA-256
`3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff`.
It contains a 15.60-second clip, not a complete multi-minute song. The entire
decoded clip is retained: 688,128 samples per channel, stereo 44.1 kHz, with no
gain, trim, downmix or resampling. The supplied original remains read-only.

`tools/stage_custom_trophy_music.py` encodes that clip as native plaintext ADX
in one detached Mobile ACB. The encoder emits an incomplete 18-byte stereo
terminal marker after the exact declared audio frames; only that marker is
removed. Strict full decoding then returns all 2,752,512 signed-16 PCM bytes.
The original native ADX header/analyzer/create/stream decoder also synthesizes
every sample, with finite non-silent PCM and correlation 0.9999971 against the
independent desktop decode. The original ACB waveform reader maps EncodeType 0
to native format 1 (ADX); the standard native voice pool supports that codec.
This cue requires no HCA cipher exception. Other HCA voices retain their policy.

The v88 bank copied native music sequence 5 but cleared its CommandIndex. That
discarded the sequence's authored cue-local routing. The corrected bank retains
CommandIndex 5 and the exact native command/string tables and ACF identity.
The referenced command is 30 bytes, SHA-256
`3e3ec7ea2219024e1615ee036ffc751ad784f27176c6c914cbd88c75553f78b6`.
No global gain, category volume, playlist or existing bank is changed. The
current asset is `Audio/trophy-user-v89.acb`, 779,816 bytes, SHA-256
`c49db9fa8935841ae025627176a180d7cc8eb812bd8ebdddeb2274dd6a294fd1`.
Its 15.6038-second recording plays once and can end before the ceremony ends.

Native PlayBgm's two zero arguments match the original victory-BGM caller.
A zero PlayBgm result means the request was queued; it does not establish
audibility. The original native CheckRequire returns `0x80000010` for an absent
tagged playback handle. Stop returning that value is now treated as already
retired only when a separate native GetStatus confirms the same result.
Other errors retain ownership and prevent duplicate playback. Raw Stop/Status
results are journaled instead of applying an undocumented boolean convention.

Only the serialized native ceremony owner observes playback. At most six
observations per handle, at 0/100/1000/4000/10000/16000 ms, read native status,
the original IsPlaying status bit 20, playback position and the existing
menu-music category's total gain. Input and rendering threads do not query or
change the mixer. All seven native binding bodies and the original ELF identity
are checked before installation. Skip, End, replacement, failure and teardown
continue to stop only the owned handle with the native 250-ms fade.

The staged bank, full native PCM proof and focused test log remain ignored in
`local-debug/trophy-presentation-v89/music-02/`. Earlier FL26 and first custom
staging evidence remain separate. The routing defect and retired-handle
classification are fixed; the v88 device log alone cannot prove which decoder
or mixer condition caused its silence. Native decoding and host ownership
checks do not establish audible output or mix balance on Switch. The next
device test and bounded playback observations remain necessary.
