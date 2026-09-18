# PES21 PC face transfer audit

Audit date: 2026-09-19. This is a format/feasibility audit against the local,
legally supplied Football Life 2026 installation and the supported PES 2021
Mobile v5.3.0 runtime. No PC or mobile game asset is stored in this repository.

## Result

Direct face copying from PES21 PC/Football Life into PES21 Mobile is **not
compatible**. A conversion pipeline is technically possible, but it is a new
mesh/material/cooking project rather than the CPK member replacement used for
kits and crests.

The audited Football Life face archive uses the Fox Engine asset family. Its
26,996-row CPK contains per-player `face.fpk`/`face.fpkd` packages and PC FTEX
maps. One inspected package has the `foxfpk` signature and embeds
`face_high.fmdl`, `hair_high.fmdl`, face/hair material names, and DDS/TGA source
references. The release mobile PAK instead exposes 2,888 player-ID-keyed UE4
packages under `Content/Assets/character/RealFace/<id>_face.uasset`, with
associated cooked exports/bulk data. These are different model containers,
material contracts, package namespaces, and runtime loaders.

Consequently, renaming `face.fpk`, copying an FMDL, or converting only its FTEX
textures cannot produce a loadable mobile face. The existing uniform converter
does not solve this: uniforms flatten a known texture atlas, while a face also
needs the skinned mesh, mobile skeleton/bone mapping, face animation or morph
contract, hair geometry/transparency, materials, LODs, and Android-cooked UE4
package metadata.

## Feasible conversion route

A one-player canary would require all of the following:

1. Resolve identity by eFootball `BaseId` plus fingerprint; never trust the
   numeric PC player ID alone.
2. Extract FPK/FPKD locally, decode `face_high.fmdl`, `hair_high.fmdl`, and the
   complete FTEX material set.
3. Retarget the mesh and weights to the exact mobile face skeleton and recreate
   its face/hair material parameters, LODs, and animation/morph expectations.
4. Cook new UE4 assets for the target Android ETC1 runtime using the compatible
   engine serialization version and the exact internal package names expected
   by `RealFace/<NativePES21Id>_*`.
5. Package the cooked `.uasset`/`.uexp`/`.ubulk` set into a detached local PAK,
   then validate boot, gameplay, replay, close-ups, lighting, hair alpha, and a
   generic-face fallback. Only after that can the process be automated.

The repository currently has no FMDL-to-mobile-skeletal-mesh converter and no
verified compatible UE4 face cooker. Therefore the status is **possible in
principle, not production-ready**. The safe production policy remains to pin
the 2,888 native mobile real-face owners by `NativePES21Id`; a mobile/UE4 face
source is materially closer than a PES21 PC Fox Engine face.

## Scope guard

Any future canary must use ignored `local-inputs/` and `local-debug/` paths.
FPK, FPKD, FMDL, FTEX, cooked face packages, extracted trees, and generated
PAKs are proprietary local inputs/artifacts and must never be committed.

