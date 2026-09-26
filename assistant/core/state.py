"""Pure assistant state machine (BUILD_PLAN section 3.3).

``next_state(state, event) -> (state, effects)`` is a pure function: no I/O, no
timers, no globals. The orchestrator interprets the returned effects. Any event
not listed for a state is ignored (state unchanged, no effects).
"""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    UNDERSTANDING = "understanding"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    RESPONDING = "responding"
    FOLLOW_UP = "follow_up"
    DICTATING = "dictating"
    MUTED = "muted"
    PAUSED = "paused"


class Event(StrEnum):
    WAKE = "wake"  # wake word detected
    HOTKEY = "hotkey"  # push-to-talk pressed
    SPEECH_START = "speech_start"  # VAD: speech began
    SPEECH_END = "speech_end"  # VAD: endpointed (1.2 s silence or 8 s max)
    TRANSCRIPT_READY = "transcript_ready"
    TRANSCRIPT_EMPTY = "transcript_empty"
    INTENT_READY = "intent_ready"  # understood, risk < CONFIRM
    INTENT_UNKNOWN = "intent_unknown"
    INTENT_FORBIDDEN = "intent_forbidden"
    CONFIRM_NEEDED = "confirm_needed"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    CONFIRM_TIMEOUT = "confirm_timeout"
    EXEC_DONE = "exec_done"
    EXEC_ERROR = "exec_error"
    RESPONSE_DONE = "response_done"  # TTS finished
    BARGE_IN = "barge_in"  # hotkey while TTS is speaking
    FOLLOWUP_TIMEOUT = "followup_timeout"
    DICTATION_START = "dictation_start"
    DICTATION_STOP = "dictation_stop"
    MUTE = "mute"
    UNMUTE = "unmute"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"  # user abort while listening/confirming


class Effect(StrEnum):
    CHIME = "chime"  # wake acknowledgement sound
    SHOW_LISTENING = "show_listening"  # overlay "Listening..."
    HIDE_OVERLAY = "hide_overlay"
    SHOW_TRANSCRIBING = "show_transcribing"
    RUN_STT = "run_stt"
    RUN_NLU = "run_nlu"
    ASK_CONFIRM = "ask_confirm"
    START_CONFIRM_TIMER = "start_confirm_timer"
    STOP_CONFIRM_TIMER = "stop_confirm_timer"
    RUN_SKILL = "run_skill"
    SPEAK = "speak"  # speak the current result text
    SPEAK_NOT_UNDERSTOOD = "speak_not_understood"
    SPEAK_REFUSAL = "speak_refusal"
    SPEAK_CANCELLED = "speak_cancelled"
    SHOW_RESULT = "show_result"
    START_FOLLOWUP_TIMER = "start_followup_timer"
    STOP_TTS = "stop_tts"  # barge-in: interrupt speech
    START_DICTATION = "start_dictation"
    STOP_DICTATION = "stop_dictation"
    SHOW_MUTED = "show_muted"
    SHOW_DICTATING = "show_dictating"


Transition = tuple[State, tuple[Effect, ...]]

_L = (Effect.CHIME, Effect.SHOW_LISTENING)
_HOTKEY_IN = (Effect.SHOW_LISTENING,)

_TRANSITIONS: dict[tuple[State, Event], Transition] = {
    # idle
    (State.IDLE, Event.WAKE): (State.LISTENING, _L),
    (State.IDLE, Event.HOTKEY): (State.LISTENING, _HOTKEY_IN),
    (State.IDLE, Event.DICTATION_START): (State.DICTATING, (Effect.SHOW_DICTATING,)),
    (State.IDLE, Event.MUTE): (State.MUTED, (Effect.SHOW_MUTED,)),
    (State.IDLE, Event.PAUSE): (State.PAUSED, ()),
    # listening
    (State.LISTENING, Event.SPEECH_START): (State.LISTENING, ()),
    (State.LISTENING, Event.SPEECH_END): (
        State.TRANSCRIBING,
        (Effect.RUN_STT, Effect.SHOW_TRANSCRIBING),
    ),
    (State.LISTENING, Event.CANCEL): (State.IDLE, (Effect.HIDE_OVERLAY,)),
    (State.LISTENING, Event.MUTE): (State.MUTED, (Effect.HIDE_OVERLAY, Effect.SHOW_MUTED)),
    (State.LISTENING, Event.PAUSE): (State.PAUSED, (Effect.HIDE_OVERLAY,)),
    # transcribing
    (State.TRANSCRIBING, Event.TRANSCRIPT_READY): (State.UNDERSTANDING, (Effect.RUN_NLU,)),
    (State.TRANSCRIBING, Event.TRANSCRIPT_EMPTY): (
        State.RESPONDING,
        (Effect.SPEAK_NOT_UNDERSTOOD,),
    ),
    (State.TRANSCRIBING, Event.EXEC_ERROR): (State.RESPONDING, (Effect.SPEAK,)),
    # understanding
    (State.UNDERSTANDING, Event.INTENT_READY): (State.EXECUTING, (Effect.RUN_SKILL,)),
    (State.UNDERSTANDING, Event.CONFIRM_NEEDED): (
        State.CONFIRMING,
        (Effect.ASK_CONFIRM, Effect.START_CONFIRM_TIMER),
    ),
    (State.UNDERSTANDING, Event.INTENT_UNKNOWN): (
        State.RESPONDING,
        (Effect.SPEAK_NOT_UNDERSTOOD,),
    ),
    (State.UNDERSTANDING, Event.INTENT_FORBIDDEN): (State.RESPONDING, (Effect.SPEAK_REFUSAL,)),
    # confirming
    (State.CONFIRMING, Event.CONFIRM_YES): (
        State.EXECUTING,
        (Effect.STOP_CONFIRM_TIMER, Effect.RUN_SKILL),
    ),
    (State.CONFIRMING, Event.CONFIRM_NO): (
        State.RESPONDING,
        (Effect.STOP_CONFIRM_TIMER, Effect.SPEAK_CANCELLED),
    ),
    (State.CONFIRMING, Event.CONFIRM_TIMEOUT): (
        State.RESPONDING,
        (Effect.STOP_CONFIRM_TIMER, Effect.SPEAK_CANCELLED),
    ),
    (State.CONFIRMING, Event.CANCEL): (
        State.RESPONDING,
        (Effect.STOP_CONFIRM_TIMER, Effect.SPEAK_CANCELLED),
    ),
    # executing
    (State.EXECUTING, Event.EXEC_DONE): (State.RESPONDING, (Effect.SPEAK, Effect.SHOW_RESULT)),
    (State.EXECUTING, Event.EXEC_ERROR): (State.RESPONDING, (Effect.SPEAK,)),
    # responding (TTS playing)
    (State.RESPONDING, Event.RESPONSE_DONE): (
        State.FOLLOW_UP,
        (Effect.HIDE_OVERLAY, Effect.START_FOLLOWUP_TIMER),
    ),
    (State.RESPONDING, Event.BARGE_IN): (State.LISTENING, (Effect.STOP_TTS, Effect.SHOW_LISTENING)),
    # follow-up window (no wake word needed)
    (State.FOLLOW_UP, Event.WAKE): (State.LISTENING, _L),
    (State.FOLLOW_UP, Event.HOTKEY): (State.LISTENING, _HOTKEY_IN),
    (State.FOLLOW_UP, Event.SPEECH_START): (State.LISTENING, (Effect.SHOW_LISTENING,)),
    (State.FOLLOW_UP, Event.FOLLOWUP_TIMEOUT): (State.IDLE, ()),
    (State.FOLLOW_UP, Event.MUTE): (State.MUTED, (Effect.SHOW_MUTED,)),
    (State.FOLLOW_UP, Event.PAUSE): (State.PAUSED, ()),
    (State.FOLLOW_UP, Event.DICTATION_START): (State.DICTATING, (Effect.SHOW_DICTATING,)),
    # dictating (wake word ignored here except "<wake word> stop", handled by NLU)
    (State.DICTATING, Event.DICTATION_STOP): (
        State.IDLE,
        (Effect.STOP_DICTATION, Effect.HIDE_OVERLAY),
    ),
    (State.DICTATING, Event.MUTE): (State.MUTED, (Effect.STOP_DICTATION, Effect.SHOW_MUTED)),
    (State.DICTATING, Event.PAUSE): (State.PAUSED, (Effect.STOP_DICTATION,)),
    # muted / paused
    (State.MUTED, Event.UNMUTE): (State.IDLE, ()),
    (State.PAUSED, Event.RESUME): (State.IDLE, ()),
}


def next_state(state: State, event: Event) -> Transition:
    """Return ``(new_state, effects)``. Pure; unhandled events are ignored."""
    return _TRANSITIONS.get((state, event), (state, ()))


def all_transitions() -> dict[tuple[State, Event], Transition]:
    """The full transition table (exposed for tests)."""
    return dict(_TRANSITIONS)
