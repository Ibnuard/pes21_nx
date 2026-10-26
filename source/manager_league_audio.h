/* Project-authored event boundary; no native player IDs or game audio data. */
#ifndef PESNX_MANAGER_LEAGUE_AUDIO_H
#define PESNX_MANAGER_LEAGUE_AUDIO_H
#include <stdint.h>

enum ManagerLeagueAudioEvent {
  MLA_PASS, MLA_SHOT, MLA_GOAL, MLA_FOUL, MLA_YELLOW, MLA_SUBSTITUTION,
  MLA_OFFSIDE, MLA_CORNER, MLA_SAVE, MLA_HALF_TIME, MLA_FULL_TIME,
  MLA_KICKOFF, MLA_EVENT_COUNT
};
enum ManagerLeagueAudioClip {
  MLA_BED, MLA_BALL_PASS, MLA_BALL_SHOT, MLA_CROWD_GOAL,
  MLA_SPEECH_SHOT, MLA_SPEECH_GOAL, MLA_SPEECH_FOUL, MLA_SPEECH_YELLOW,
  MLA_SPEECH_SUBSTITUTION, MLA_SPEECH_OFFSIDE, MLA_SPEECH_CORNER,
  MLA_SPEECH_SAVE, MLA_SPEECH_HALF_TIME, MLA_SPEECH_FULL_TIME,
  MLA_SPEECH_KICKOFF, MLA_CLIP_COUNT
};
typedef struct ManagerLeagueAudioFrame {
  uint64_t fixture_token, monotonic_ms;
  uint32_t timeline_serial, position_ms, visible_watch, replay, paused;
  /* Stable tape index+1; zero means no event. Do not use an animation counter. */
  uint32_t event_serial, event_at_ms, event_kind, event_side;
} ManagerLeagueAudioFrame;

/* Publication performs only a short snapshot copy. All native mixer activity
 * is deferred to manager_league_audio_native_pump on its serialized owner. */
void manager_league_audio_publish(const ManagerLeagueAudioFrame *frame);
#endif
