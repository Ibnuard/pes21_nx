#ifndef PESNX_MANAGER_LEAGUE_AUDIO_POLICY_H
#define PESNX_MANAGER_LEAGUE_AUDIO_POLICY_H
#include <string.h>
#include "manager_league_audio.h"

typedef struct ManagerLeagueAudioOps {
  int (*play)(void *, uint32_t clip, uint64_t *handle);
  int (*stop)(void *, uint64_t handle, uint32_t fade_ms);
  uint32_t (*duration)(void *, uint32_t clip);
  void *context;
} ManagerLeagueAudioOps;
typedef struct ManagerLeagueAudioVoice { uint64_t handle, until_ms; } ManagerLeagueAudioVoice;
typedef struct ManagerLeagueAudioPolicy {
  ManagerLeagueAudioOps ops;
  ManagerLeagueAudioVoice bed, speech, effect;
  uint64_t fixture, last_now, speech_gap_until, next_event_ms,announced_fixture;
  uint32_t anchored, timeline_serial, position, replay, cursor, bed_failed;
  uint32_t stop_failed, played_events, stale_events, dropped_speech;
} ManagerLeagueAudioPolicy;

static inline int mla_stop_voice(ManagerLeagueAudioPolicy *state,
    ManagerLeagueAudioVoice *voice) {
  if (!voice->handle) return 1;
  if (!state->ops.stop || state->ops.stop(state->ops.context, voice->handle, 100u)) {
    state->stop_failed = 1u;
    return 0; /* Never overwrite a handle whose native stop was not admitted. */
  }
  memset(voice, 0, sizeof(*voice));
  return 1;
}
static inline int mla_stop_all(ManagerLeagueAudioPolicy *state) {
  int result = mla_stop_voice(state, &state->speech);
  result = mla_stop_voice(state, &state->effect) && result;
  return mla_stop_voice(state, &state->bed) && result;
}
static inline int mla_start_voice(ManagerLeagueAudioPolicy *state,
    ManagerLeagueAudioVoice *voice, uint32_t clip, uint64_t now) {
  if (state->stop_failed || voice->handle || !state->ops.play || !state->ops.duration) return 0;
  const uint32_t duration = state->ops.duration(state->ops.context, clip);
  if (!duration || duration > 30000u) return 0; /* Missing/unreviewed clip stays silent. */
  uint64_t handle = 0;
  const int result = state->ops.play(state->ops.context, clip, &handle);
  if (result || !handle) {
    if (handle) {
      voice->handle = handle;
      mla_stop_voice(state, voice);
    }
    return 0;
  }
  voice->handle = handle;
  voice->until_ms = clip == MLA_BED ? UINT64_MAX : now + duration + 100u;
  return 1;
}
static inline uint32_t mla_speech_for_event(uint32_t event) {
  static const uint8_t clips[MLA_EVENT_COUNT] = {
    MLA_CLIP_COUNT, MLA_SPEECH_SHOT, MLA_SPEECH_GOAL, MLA_SPEECH_FOUL,
    MLA_SPEECH_YELLOW, MLA_SPEECH_SUBSTITUTION, MLA_SPEECH_OFFSIDE,
    MLA_SPEECH_CORNER, MLA_SPEECH_SAVE, MLA_SPEECH_HALF_TIME,
    MLA_SPEECH_FULL_TIME, MLA_SPEECH_KICKOFF
  };
  return event < MLA_EVENT_COUNT ? clips[event] : MLA_CLIP_COUNT;
}
static inline void manager_league_audio_step(ManagerLeagueAudioPolicy *state,
    const ManagerLeagueAudioFrame *frame) {
  if (!state || !frame) return;
  if (!frame->visible_watch || frame->paused || !frame->fixture_token) {
    if (!state->stop_failed) mla_stop_all(state);
    state->anchored = 0;
    return;
  }
  if (state->stop_failed) return;
  const uint64_t now = frame->monotonic_ms;
  const uint32_t changed = !state->anchored || state->fixture != frame->fixture_token ||
      state->timeline_serial != frame->timeline_serial || state->replay != !!frame->replay ||
      now < state->last_now || frame->position_ms < state->position ||
      frame->position_ms - state->position > 2000u;
  if (changed) {
    if (!mla_stop_all(state)) return;
    state->fixture = frame->fixture_token;
    state->timeline_serial = frame->timeline_serial;
    state->replay = !!frame->replay;
    state->cursor = frame->event_serial;
    state->position = frame->position_ms;
    state->last_now = now;
    state->anchored = 1u;
    state->bed_failed = 0;
    state->speech_gap_until = now;
    state->next_event_ms = now;
    /* Opening late, seeking, resuming and switching modes anchor the cursor.
     * Historical speech/SFX are not replayed as though they just happened. */
    if (!mla_start_voice(state, &state->bed, MLA_BED, now)) state->bed_failed = 1u;
    if(!frame->replay && state->announced_fixture!=frame->fixture_token) {
      state->announced_fixture=frame->fixture_token;
      if(frame->position_ms<=1000u)
        mla_start_voice(state,&state->speech,MLA_SPEECH_KICKOFF,now);
    }
    return;
  }
  state->position = frame->position_ms;
  state->last_now = now;
  if (state->bed.handle && now >= state->bed.until_ms) mla_stop_voice(state, &state->bed);
  if (state->speech.handle && now >= state->speech.until_ms) {
    mla_stop_voice(state, &state->speech);
    state->speech_gap_until = now + 350u;
  }
  if (state->effect.handle && now >= state->effect.until_ms) mla_stop_voice(state, &state->effect);
  if (!state->bed.handle && !state->bed_failed &&
      !mla_start_voice(state, &state->bed, MLA_BED, now)) state->bed_failed = 1u;
  if (!frame->event_serial || frame->event_serial == state->cursor) return;
  const uint32_t previous = state->cursor;
  state->cursor = frame->event_serial;
  if (frame->event_serial <= previous || frame->event_at_ms > frame->position_ms ||
      frame->position_ms - frame->event_at_ms > 1200u || frame->event_kind >= MLA_EVENT_COUNT ||
      now < state->next_event_ms) {
    ++state->stale_events;
    return;
  }
  ++state->played_events;
  state->next_event_ms = now + 250u; /* Bounds accepted fades under malformed event floods. */
  uint32_t effect = MLA_CLIP_COUNT;
  if (frame->event_kind == MLA_PASS) effect = MLA_BALL_PASS;
  if (frame->event_kind == MLA_SHOT || frame->event_kind == MLA_SAVE) effect = MLA_BALL_SHOT;
  if (frame->event_kind == MLA_GOAL) effect = MLA_CROWD_GOAL;
  if (effect < MLA_CLIP_COUNT && mla_stop_voice(state, &state->effect))
    mla_start_voice(state, &state->effect, effect, now);
  if (frame->replay) return; /* Replay is supporter and ball audio only. */
  const uint32_t speech = mla_speech_for_event(frame->event_kind);
  if (speech >= MLA_CLIP_COUNT) return;
  if (frame->event_kind == MLA_GOAL && state->speech.handle)
    mla_stop_voice(state, &state->speech); /* Goal supersedes an obsolete shot line. */
  if (state->speech.handle || now < state->speech_gap_until) {
    ++state->dropped_speech;
    return; /* No queued backlog and no overlapping commentators. */
  }
  mla_start_voice(state, &state->speech, speech, now);
}
#endif
