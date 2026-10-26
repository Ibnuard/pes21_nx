# Ceremony music and PC effect audit (v88)

The user selected the locally owned FL26 Cup celebration music for the first
audio trial. Its exact `BGM1_ORG_CHAMP_CP` graph resolves to AWB recording 49:
1,582,342 bytes, plaintext HCA, stereo 48 kHz, 5,429,646 samples, with the
authored loop. The source recording SHA-256 is
`afa106ddb741b50e373c75642a37306d01895a75b45b29bbb790cbaa13ddabdf`.

`tools/stage_trophy_music.py` reads only that recording range from the local
FL26 archive. It constructs one private cue in the native Mobile music-bank
schema, retaining Mobile's ACF identity and the exact FL26 recording/loop.
The existing music banks, commentary, playlists, volumes and CPKs are unchanged.
Full desktop decoding and graph/payload roundtrip checks precede staging.
The optional detached asset `Audio/trophy-fl26-v88.acb` is 1,588,072 bytes;
its SHA-256 is
`a1901ec2bea1878751d21eaceaf4b4136f2ecbd0f3974f7b73ff3728a0976403`.
Only generated size/hash metadata belongs in the public tree.

The adapter checks the native MountData, PlayBgm, Stop and IsExisting bodies
in readable backing and retains executable addresses for later calls. The
five-argument MountData overload supplies the native group/flag defaults.
Music starts once per match token after native StartDemoEvent, with both props
ready and the winner checked. The serialized owner stops only its playback
handle with a 250-ms native fade on Skip, native End, failure, replacement,
destruction or match teardown. Input/render threads do not call the mixer.
Missing or damaged optional music leaves the ceremony running.

The bounded memory bank remains cached while mounted until process exit.
This avoids freeing data beneath an asynchronous native fade; it does not
retain a live music handle after ceremony cleanup. The plaintext decoder
exception requires a successfully mounted owned bank and the exact complete
260-byte HCA metadata fingerprint. Other voices keep their existing cipher
behavior. Native/global cipher and volume settings are unchanged.

The PC `end_trophy_01_fx.fdc` contains four typed effect records and no named
resources. Its filename does not establish the exact visible PC effect.
In the supported Mobile library, SetEffect only changes a work flag and the
effect change/delete/camera methods are stubs. Restoring that FDC alone cannot
render fireworks. A small podium-scoped effect would need a separate explicit
renderer implementation and device validation; v88 does not claim PC FX.

Host ownership tests and desktop decoding do not establish audible playback,
mix balance or performance on Switch. Those require the next device test.
