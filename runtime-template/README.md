# Runtime template

Copy the completed contents of this directory to
`sdmc:/switch/pes21_nx/`. The committed `.DONOTDELETE` files preserve the
tested directory layout without redistributing game data.

## Required files

| Runtime path | Source |
| --- | --- |
| `pes21_nx.nro` | Build this repository. |
| `libUE4.so` | Extract `lib/arm64-v8a/libUE4.so` from the compatible APK. |
| `libafp-core.so` | Extract `lib/arm64-v8a/libafp-core.so` from the APK. |
| `libavs2-core.so` | Extract `lib/arm64-v8a/libavs2-core.so` from the APK. |
| `PesMobile/Content/Paks/PesMobile-Android_ETC1.pak` | Extract from the main OBB ZIP. |
| `patch.305030001.jp.nyan2021.pesam.obb` | Copy the compatible patch OBB unchanged. |
| `Download/dt530_mobile_*_all.cpk` | Extract the ten locale CPK files listed in `runtime-manifest.json` from the patch OBB. |
| `assets/responses/*.bin` | Generate from your APK with the public builder below. |

Generate the response payloads after installing the two Python dependencies:

```powershell
python -m pip install -r tools/offline-response-requirements.txt
python tools/build_offline_responses.py PES21.apk runtime-template/assets/responses
```

The builder reads all original response JSON documents directly from the APK,
applies only the PES 2021 NX existing-account compatibility overrides, writes
the 48 encrypted `.bin` files used by the JNI HTTP shim, and verifies every
output size. Add `--keep-json` only for local debugging; JSON files are not
required at runtime.

`SaveData/` is populated by the game and must not be shared between users.
`UE4Game/.../Paks/` is retained as an optional compatibility mirror seen in
the tested runtime; the wrapper's required PAK path is the shorter
`PesMobile/Content/Paks/` path.

The APK itself, the main OBB after its PAK is extracted, debug logs,
`offline_keystore.p12`, and `login-identifier.txt` are not required runtime
payloads. Never commit certificates, private keys, saved accounts, or game
archives to this repository.
