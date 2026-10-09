# Indonesia team commentary

The FL26 migration gives Indonesia logical ID 5750 while retaining native
storage slot 1164. The old English commentary bank still contains Israel's
1164 cues. Renaming Team.bin does not change the native team-name label ID.
This report is about team commentary only; it makes no claim about player
name lookup or player asset ownership.

## v8 playback correction

**Accepted reference, 2026-10-09:** the user confirms Indonesia playback is
fixed with the v8 decoder policy, retained by the Day-roof build. Keep the
604,036-byte `Commentary/indonesia.nxcp` with SHA-256
`762524358c15ccab63282aa6abf1031ad4dc5746bfb0badf69e5cc64006deed8`
as the comparison for later commentary work. An ignored copy is retained in
`local-checkpoints/accepted-2026-10-09/`. The acceptance supersedes the pending
playback status below for the user's tested calls, without claiming coverage
of all speakers or match contexts. New cues must preserve speaker/source
identity and explicitly verify plaintext versus encrypted HCA handling; never
apply the plaintext exception to an unaudited recording or all decoder instances.

The user tested v7 on Switch and heard a brief distorted sound followed by
silence when Indonesia was called. This supersedes v7's pending playback
status below. The source recordings and the final embedded ACB both decode
correctly with the independent [vgmstream decoder](https://github.com/vgmstream/vgmstream);
container validity alone did not verify the game's playback path.

The supported native HCA codec installs its global decryption table before
each `HCADecoder_DecodeHeader` call. With `ciph=0`, that header reader retains
a custom table; `HCADecoder_SetFrameData` then substitutes the plaintext
packet bytes through it. The mobile recordings are encrypted, whereas the
two FL26 Indonesia recordings are plaintext. A local execution of the native
packet reader reproduces the corruption with a synthetic nonidentity cipher,
without extracting or embedding any game decryption key.

v8 intercepts the fingerprint-checked header-decoder PLT entry. While the
Indonesia catalog and a successfully patched team bank are active, it
recognizes only the two audited 96-byte plaintext headers, including split
input buffers, and clears that decoder instance's table through the native
setter before reading the header. It does not change the global table. The
codec installs the normal table again before each subsequent header. Other
headers, incomplete inputs, other catalogs and unpatched banks pass through.
There is no change to the audio recordings or the v7 delta file.

Tests cover both speakers, every header split/truncation, each corrupted
header byte, four mount slots, inactive/unmount states and argument/result
forwarding. The native packet-reader test first reproduces corruption and
then verifies all 74 HCA frames byte-for-byte after clearing the per-decoder
table. It uses optional owned inputs, pyelftools and Unicorn, isolated in a
child process so native JIT exceptions cannot interrupt unrelated tests.
This validates packet handling, not Switch audio-device playback.

## Audited behavior and asset policy

In the supported Mobile v5.3.0 library, `CreateTeamNameLabelInfo` extracts the
native team ID and passes it to `CreateTeamNameLabel`. The wrapper intercepts
only that label builder's PLT call, translating 1164 to 5750 when the compiled
catalog actually maps Indonesia 5750 to slot 1164. Original Israel catalogs,
other teams, explicit edited-name IDs, database records, and player IDs are
unchanged. Native missing-cue checks remain in control of unavailable phrases.

The user's local English FL26 `dt41_eng_all.cpk` contains two explicit
Indonesia recordings: the A1 and B1 `T0_R5750` cues (890 ms and 669 ms).
The inspected mobile English override has no 5750 team-name cue. Its two
plain 1164 team-name cues are replaced with those exact unencrypted FL26 HCA
recordings, preserving speaker identity. No voice is synthesized, no player
audio is borrowed, and no other Israel-specific phrase is relabeled as
Indonesia. Contexts without an Indonesia cue follow native missing-cue
behavior; this is not a complete set of new team-specific commentary lines.

All source sound banks and the generated audio delta remain local and ignored.
Only the wrapper, staging tool, tests, and these findings are public.

## Local staging

```powershell
python tools/stage_indonesia_commentary.py `
  --mobile-cpk dist/pes21_nx/Download/dt510_mobile_eng_all.cpk `
  --fl26-cpk 'D:/Games/SP Football Life 2026/Data/dt41_eng_all.cpk' `
  --output local-debug/indonesia-commentary-v8
python -m pytest tests/test_team_commentary.py -q
```

Use a new output directory when reproducing; staging rejects existing output.
The mobile CPK path must be the actual installed English override. A supported
legacy TOC name defect is recovered for reading only. The tool requires the
audited one-to-one mobile cue/sequence/track/synth/wave graph and no existing
memory AWB. Unexpected layouts or source headers outside the wrapper's
audited plaintext policy fail staging instead of guessing compatibility.

The generated `Commentary/indonesia.nxcp` is a 604,036-byte delta, rather than
a replacement for the multi-gigabyte sound CPK. It embeds a two-recording
memory AWB, promotes the waveform Streaming field to per-row storage, and
keeps cue-name rows sorted. The original streaming AWB stays byte-for-byte
untouched. Of 45,450 original cues, 45,448 retain their cue records, waveform
metadata, names and references. The original graph tables are byte-identical.

The mount hook matches the `00_TEAM.awb` basename and checks the exact original
ACB's length and FNV-1a checksum before applying bounded, ordered delta ranges.
A second checksum verifies the result. The current base ACB SHA-256 is
`704fa0f45d4998c36e959e2f6d32329099683c95dcd41a378ad90b39b3e998ff`.
The staging report also records result, delta and source-recording SHA-256s.

Each patched mount owns its buffer until native unmount succeeds. Four bounded
slots support overlapping loads, and each rematch reconstructs pristine bytes
instead of reusing CRI-mutated work areas. Reservation before native unmount
protects against immediate mount-ID reuse. Missing, damaged or mismatched
deltas retain the original audio bank; a native patch-mount failure retries
the original bank. In those cases Indonesia's unmapped name cues are skipped
instead of falling back to Israel.

The additional live ACB buffer is 4,725,536 bytes per patched mount. No audio
work runs on each frame. The CPK manifest and paired database build ID do not
change because this optional delta is loaded by the wrapper.

## Validation and device check

The focused tests cover all 16,384 native IDs, edited-name isolation, damaged
and truncated deltas, range bounds, mount failure, four simultaneous mounts,
failed unmount, immediate mount-ID reuse, and twelve rematches. Local asset
checks rebuild the delta deterministically, compare every unaffected cue and
waveform, preserve the original graph, and verify both embedded recordings.
The four PLT fingerprints are checked against the user-owned ELF. Both source
HCA recordings also decoded successfully with FFmpeg.

Local asset tests report unavailable fixtures when the owned CPKs, generated
delta or ELF are absent. `PESNX_FL26_COMMENTARY_CPK` can point the local test at
the user's FL26 English CPK. Raw disassembly and extracted audio are not public
fixtures and are not required by the synthetic runtime tests.

The v8 candidate uses the same `e861c583ec78e9ae` NRO/loose-data pairing as v6,
keeps the result UI, and restores v5's lighting behavior after the device
regression reported for v7. Install the NRO
plus `Commentary/indonesia.nxcp` under the existing `switch/pes21_nx` directory.
No OBB, PAK, CPK, roster or save replacement is needed. The v7 Commentary file
can be retained; it is identical in v8. Switch playback of v8 still requires
validation. Check Indonesia at home and away, plain team-name calls from
both speakers, goals, the second half, rematch, then a match with two unrelated
teams. Restore the previous NRO and remove the optional Commentary file to
roll back.
