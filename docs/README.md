# Documentation index

The repository root contains only the standard project entry documents.
Subsystem notes and historical implementation audits live here.

## Manager League review

- [Random preferences, analog scrolling, loading UI and production assets v100](REVIEW_V100.md)
- [Watch details, paid packs, ranking resets and honours v99](MANAGER_REVIEW_V99.md)
- [Manager PCM output routing v99](MANAGER_LEAGUE_AUDIO_V99.md)
- [Custom trophy song gain v99](TROPHY_AUDIO_GAIN_V99.md)
- [Signal Iduna stair and portal restoration v99](STADIUM_SIGNAL_STAIRS_V99.md)
- [Currency, club profiles and two leagues per week v98](MANAGER_REVIEW_V98.md)
- [Signal Iduna stand surfaces v98](STADIUM_SIGNAL_SURFACES_V98.md)
- [Signal Iduna and Camp Nou pitch alignment v98](STADIUM_PITCH_ALIGNMENT_V98.md)
- [Local PIN accounts and trophy music v97](MANAGER_REVIEW_V97.md)

## Data and roster migration

- [PES21 NX master data catalog](MASTER_DATA_CATALOG.md)
- [PESDB eFootball identity](PESDB_EFOOTBALL_IDENTITY.md)
- [PESDB import](PESDB_EFOOTBALL_IMPORT.md)
- [PESDB apply](PESDB_EFOOTBALL_APPLY.md)
- [PESDB runtime rosters](PESDB_RUNTIME_ROSTERS.md)
- [PES21 player recreation analysis](PES21ReCreateOrderPlayerAnlisys.md)
- [PES21 PC face transfer audit](PES21_PC_FACE_TRANSFER_AUDIT.md)
- [Realface geometry/performance audit and Lite recommendation](REALFACE_PERFORMANCE_AUDIT.md)
- [Realface Lite v34, stadium stair repair and Cunha skin policy](REALFACE_LITE_V34.md)
- [Barcelona/MU: v34 device feedback and remaining realface render costs](REALFACE_RENDER_FOLLOWUP_V35.md)
- [Realface Mobile v35 canary recipe](REALFACE_MOBILE_CANARY_V35.md) — strict head budget, merged eye atlas, and offline hair surface conversion.
- [Realface v36 surface correction](REALFACE_SURFACE_V36.md) — isolated neutral normal map, unchanged v35 geometry and automated package validation.
- [Realface v37 facial detail and compact hair](REALFACE_REFINEMENT_V37.md) — visible UV distortion audit, protected mouth features and joined hair under the same head budget.
- [Barcelona realface conversion and automation plan](REALFACE_BARCA_PLAN.md)
- [eFootball10 player conversion](EFOOTBALL10_PLAYER_CONVERSION.md)
- [Inter Miami original-ID experiment](INTER_MIAMI_ORIGINAL_ID_EXPERIMENT.md)

## Kits, badges, and licensing

- [Football Life 2026 kits and logos](FOOTBALL_LIFE_2026_KITS_LOGOS_TO_MOBILE.md)
- [Stable kits and logos migration](KITS_LOGOS_STABLE_MIGRATION.md)
- [English and Spanish license pack](ENG_SPA_LICENSE_PACK.md)
- [Serie A license pack](SERIE_A_LICENSE_PACK.md)
- [National-team kit pack](NATIONAL_TEAM_KIT_PACK.md)

## Runtime, controls, and UI

- [Accepted v48 performance checkpoint and startup audit](RENDER_AUDIT_V48.md) — user-reported stable 60 FPS, removed release pixel probes, and first-launch-after-update blinking still under investigation.
- [Render stability and mixed model quality v47](RENDER_STABILITY_V47.md) — private overlay vertex state and native Standard players only when High graphics is selected.
- [Stadium pacing and balanced faces v46](STADIUM_FACE_SWEETSPOT_V46.md) — v45 device evidence, repeated blending-state suppression and a controlled 5k head target with explicit retained originals.
- [Remaining real-face pacing v44](REALFACE_PACING_V44.md) — v43 device feedback, explicit missing timing data and removal of release clock/TLS logging atomics without changing face quality.
- [Whole-player blinking isolation v43](REALFACE_WHOLE_PLAYER_V43.md) — supplied A/B log findings, corrected mesh snapshots and GL cache/buffer control with v41 face quality retained.
- [Real-face runtime isolation v42](REALFACE_RUNTIME_V42.md) — suspended V2/entrance, head-load snapshots and asynchronous GPU/CPU comparison with v41 quality retained.
- [Wrapper overhead v45](WRAPPER_OVERHEAD_V45.md) — cached native thread IDs, single-pass buffer free lists and native pre-match preview reveal, with v41 face quality retained.
- [Stadium V2: native Stadium framing with custom tracking](STADIUM_V2_CAMERA.md)
- [Native Stadium and Pitch Side camera baseline v33](FL26_NATIVE_CAMERAS_V33.md)
- [Accepted roof shadow v20 checkpoint: cheaper flat regions with the same player shading](ROOF_SHADOW_COST_V20.md)
- [Day frame pacing v19: cached weather lighting and shader uniforms](DAY_FRAME_PACING_V19.md)
- [Referee v18: owned Low renderer and native kickoff placement](MATCH_REVIEW_V18.md)
- [FL26 referee behavior and native motion-bank audit v53](REFEREE_FL26_AUDIT_V53.md)
- [Match review v17: preset flow, Anfield camera clearance and referee cost](MATCH_REVIEW_V17.md)
- [Match review v16: Game Plan, stadium, referee and local rematch](MATCH_REVIEW_V16.md)
- [Competition modes plan: Match, Cup, League, and Master League](COMPETITION_MODES_PLAN.md)
- [FL26 cinematics and trophy integration boundaries](FL26_CINEMATICS_CANARY.md)
- [Trophy ceremony readiness and device test plan](TROPHY_CEREMONY_TEST_PLAN.md) — reproducible asset audit, missing runtime gates, and normal/penalty/Skip final scenarios.
- [MINI-GAME: Football Triple Triad and Mini Soccer concepts](MINI-GAME.md)
- [NRO launcher icon and NSP forwarder notes](NRO_ICON.md)
- [Loose CPK canary](LOOSE_CPK_CANARY.md)
- [Full loose CPK runtime](LOOSE_CPK_FULL.md)
- [Indonesia team commentary](TEAM_COMMENTARY.md)
- [Yamal and Raphinha player commentary canary v53](PLAYER_COMMENTARY_V53.md)
- [Native PES21 referee candidate v54](REFEREE_NATIVE_V54.md)
- [Balanced English/Spanish league real-face automation v55](REALFACE_LEAGUE_BALANCED_V55.md)
- [FL26 referee position controller audit](REFEREE_PC_TARGET_AUDIT_V54.md)
- [Known issues](KNOWN_ISSUES.md)
- [HUD render audit](HUD_RENDER_AUDIT.md)
- [Competition scoreboards and native weather audit](SCOREBOARD_WEATHER_AUDIT.md)
- [Native weather and competition scoreboard implementation](NATIVE_WEATHER_SCOREBOARDS.md)
- [Stadium roof toggle, camera and performance](STADIUM_ROOF_CAMERA.md)
- [Native mapping baseline](NATIVE_MAPPING_BASELINE_V1.md)
- [Native pad lab result](NATIVE_PAD_LAB_RESULT.md)
- [Visual stability test](STABILITY_VISUAL_TEST.md)

Files not listed above remain historical implementation notes and can be
located by subsystem name in this directory.
