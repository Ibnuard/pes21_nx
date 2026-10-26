# Manager League event audio v94

Historical baseline. The v94 device test admitted requests but remained silent.
See [v95 audio evidence and candidate](MANAGER_REVIEW_V95.md#native-audio-evidence-and-candidate)
for the current routing experiment and dedicated status/position journal.

The optional dot-match adapter requests generic commentary for current Live
events through the existing native mixer. Replay requests only supporter and
ball sounds. The visual simulation remains usable when the optional bank,
native ABI or native request is unavailable. Switch audibility is not established
by these host checks.

`manager_league_audio_publish` copies a small independent frame. The native
owner calls `manager_league_audio_native_pump`; render and input publication
perform no native calls, allocation or file I/O. A fixture token and stable tape
event index prevent duplicate phrases. Entering late, seeking, changing replay
mode, resuming or crossing a timeline serial anchors the current cursor without
playing historical events. A missed publication expires after two seconds.
Exit and pause stop owned handles. There is no queued commentary backlog:
obsolete/busy phrases are omitted, and a goal supersedes a shot phrase.

The detached bank contains thirteen original FL26 recordings: one looped
supporter layer, inside-foot and shot contacts, one goal-reaction layer and nine
generic English lines for shot, goal, contact/referee verdict, yellow card,
substitution, offside, corner, save and kickoff. Each speech recording was
individually transcribed locally and reviewed for generic event meaning. Numeric
cue labels do not establish meaning. No player/team names, fixed score claims,
competition claims or synthetic speech are admitted. Half-time and full-time
speech remain absent; crowd ambience continues until the view exits.

The source cue graphs, selected terminal waveform, exact payload and header
hashes are recorded in the ignored per-recording review. SFX/cheers use one
inspected source layer, not the complete PC layered mix. Source CPKs, streaming
AWBs and their existing recordings are read only; only bounded individual
ranges are read. All HCA payloads, sample/channel/rate metadata, the bed's loop
header/extension and indefinite looped cue length remain exact. No recording is
reencoded, trimmed or repainted. The ordinary Mobile ACB schema and ACF identity
provide the private cue graph. New cue-local volume and MasterOut bus commands
use the native command forms inspected in Mobile's Movement/cheer/music banks.
They do not change global/category gains or a playlist. Gains are conservative:
bed 0.10, ball contacts 0.30, goal crowd 0.18 and speech 0.65.

The adapter does not create an audio device or a voice pool. It uses the native
HCA pool and leaves the accepted trophy WAVE pool and recording unchanged. Five
complete native function bodies are checked against the pinned Mobile library
in readable backing before executable aliases become call targets. Native
`Interface::Play(name, out, 0, 0, 0)` supplies a direct cue request, not BGM
playlist handling. A zero result proves request admission, not audible sound.
The private mounted buffer stays alive to process exit so a native fade can
never outlive its source. Failed mounts release only unregistered input;
unexpected successful mount IDs retain their now registered buffer. A stopped
handle is retired normally only for the proven `0x80000010` result confirmed by
native status; unknown stop failures retain ownership and disable further play.

The plaintext HCA exception is limited to complete 96-byte fingerprints of
these exact recordings while this owned bank is mounted. Unrelated HCA headers
retain native decoder behavior. This adds no decoder replacement or broad cipher
bypass. The optional bank must be included in the candidate at
`Audio/manager-league-v94.acb` and match the compiled metadata catalog.

Focused tests compile the actual policy and runtime include, check native
function bodies against the owned library, execute the original direct-Play
wrapper to observe its request arguments, execute original HCA header/packet
methods for all thirteen recordings, and independently decode each full HCA
with FFmpeg. They cover once-only events, goal priority, replay speech silence,
late seeks, pause/exit, missing roles, source provenance, corrupt/missing bank,
mount lifetime, split headers, header corruption, stale publication and retained
handles after stop failure. The final queue in the native wrapper probe is
stubbed; no host probe executes an audio device. Device listening remains
required for actual mixer audibility, balance and transitions.
