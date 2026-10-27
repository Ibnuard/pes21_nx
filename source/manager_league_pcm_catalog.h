/* Exact reviewed v96 PCM locations only; no recordings embedded. */
#ifndef PESNX_MANAGER_LEAGUE_PCM_CATALOG_H
#define PESNX_MANAGER_LEAGUE_PCM_CATALOG_H
typedef struct MlaPcmClip { uint32_t wave_offset, frames; } MlaPcmClip;
static const MlaPcmClip mla_pcm_clips[MLA_CLIP_COUNT] = {
  {5920u, 1007977u}, /* bed */
  {4037888u, 3659u}, /* ball_pass */
  {4052576u, 8602u}, /* ball_shot */
  {4087040u, 1439744u}, /* crowd_goal */
  {9846080u, 56907u}, /* shot */
  {10073760u, 141979u}, /* goal */
  {10641728u, 124256u}, /* foul */
  {11138816u, 171823u}, /* yellow */
  {11826176u, 75505u}, /* substitution */
  {12128256u, 84533u}, /* offside */
  {12466432u, 124928u}, /* corner */
  {12966208u, 123833u}, /* save */
  {0u, 0u}, /* half_time */
  {0u, 0u}, /* full_time */
  {13461600u, 111593u}, /* kickoff */
};
#endif
