# Manager PIN and trophy volume v97

This revision contains only the requested account-input and trophy-music
follow-up. COM-versus-COM, native network synchronization, recording workers
and alternative 3D viewers are deferred at the user's request. The existing
scheduled dot broadcast remains unchanged.

- Login uses User ID and exactly four numeric PIN digits. A controller keypad
  uses the existing Master League artwork and layout primitives, masks entered
  digits, supports delete/cancel, and requires an explicit confirmation. New
  PIN creation includes a second entry. See [PIN handling](MANAGER_PIN_V97.md).
- An existing v96 password verifier requires one successful old-password
  verification before it can be replaced by a PIN verifier. Earlier profiles
  without credentials create a PIN directly. Club, wallet, players and match
  archives are preserved. Credentials remain local salted verifiers; this does
  not implement backend authentication or global unique User IDs.
- The clean user-supplied trophy recording gains 6 dB relative to v94. Its
  owned cue attenuation changes from -12 dB to -6 dB, applied once before
  encoding from the original PCM. Global music and commentary volumes remain
  unchanged. See [audio integrity and headroom](TROPHY_AUDIO_GAIN_V97.md).

Host tests cover the production PIN handlers, password migration and failure
paths, independent hash/KDF vectors, unchanged account data, native-art layout
budgets, and the new trophy bank's gain, full PCM decode and native HCA packet
admission. Host verification is not Switch listening or controller acceptance.
The native CPU-ownership research and trial code remain private, inactive
experiments; they do not establish synchronized 3D playback.
