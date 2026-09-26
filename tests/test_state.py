"""State machine tests: every transition exercised (BUILD_PLAN §3.3, 100% cov)."""

from __future__ import annotations

import itertools

from assistant.core.state import Effect, Event, State, all_transitions, next_state


def test_every_transition_returns_valid_values() -> None:
    """Every (state, event) pair — defined or not — returns a valid state + effects."""
    for state, event in itertools.product(State, Event):
        new_state, effects = next_state(state, event)
        assert isinstance(new_state, State)
        assert isinstance(effects, tuple)
        assert all(isinstance(e, Effect) for e in effects)


def test_unhandled_events_are_ignored() -> None:
    """Any pair not in the table is a no-op (state unchanged, no effects)."""
    defined = set(all_transitions())
    for state, event in itertools.product(State, Event):
        if (state, event) in defined:
            continue
        new_state, effects = next_state(state, event)
        assert new_state == state
        assert effects == ()


def test_full_table_shape() -> None:
    """Sanity: the table exists and every key uses valid enum members."""
    table = all_transitions()
    assert table
    for (state, event), (new_state, effects) in table.items():
        assert isinstance(state, State)
        assert isinstance(event, Event)
        assert isinstance(new_state, State)
        assert isinstance(effects, tuple)


# --- behavioural assertions for the flows in §3.3 / §1.2 --------------------

def test_wake_cycle_to_transcribing() -> None:
    s, fx = next_state(State.IDLE, Event.WAKE)
    assert s is State.LISTENING
    assert Effect.CHIME in fx and Effect.SHOW_LISTENING in fx
    s, fx = next_state(s, Event.SPEECH_END)
    assert s is State.TRANSCRIBING
    assert Effect.RUN_STT in fx


def test_safe_intent_runs_immediately() -> None:
    s = State.UNDERSTANDING
    s, fx = next_state(s, Event.INTENT_READY)
    assert s is State.EXECUTING and Effect.RUN_SKILL in fx
    s, fx = next_state(s, Event.EXEC_DONE)
    assert s is State.RESPONDING
    assert Effect.SPEAK in fx and Effect.SHOW_RESULT in fx
    s, fx = next_state(s, Event.RESPONSE_DONE)
    assert s is State.FOLLOW_UP
    assert Effect.START_FOLLOWUP_TIMER in fx and Effect.HIDE_OVERLAY in fx


def test_confirm_cycle_yes_no_timeout() -> None:
    s, fx = next_state(State.UNDERSTANDING, Event.CONFIRM_NEEDED)
    assert s is State.CONFIRMING
    assert Effect.ASK_CONFIRM in fx and Effect.START_CONFIRM_TIMER in fx

    yes, yfx = next_state(s, Event.CONFIRM_YES)
    assert yes is State.EXECUTING
    assert Effect.STOP_CONFIRM_TIMER in yfx and Effect.RUN_SKILL in yfx

    for ev in (Event.CONFIRM_NO, Event.CONFIRM_TIMEOUT, Event.CANCEL):
        ns, nfx = next_state(s, ev)
        assert ns is State.RESPONDING
        assert Effect.SPEAK_CANCELLED in nfx and Effect.STOP_CONFIRM_TIMER in nfx


def test_unknown_and_forbidden() -> None:
    s, fx = next_state(State.UNDERSTANDING, Event.INTENT_UNKNOWN)
    assert s is State.RESPONDING and Effect.SPEAK_NOT_UNDERSTOOD in fx
    s, fx = next_state(State.UNDERSTANDING, Event.INTENT_FORBIDDEN)
    assert s is State.RESPONDING and Effect.SPEAK_REFUSAL in fx
    s, fx = next_state(State.TRANSCRIBING, Event.TRANSCRIPT_EMPTY)
    assert s is State.RESPONDING and Effect.SPEAK_NOT_UNDERSTOOD in fx


def test_barge_in_interrupts_tts() -> None:
    s, fx = next_state(State.RESPONDING, Event.BARGE_IN)
    assert s is State.LISTENING
    assert Effect.STOP_TTS in fx and Effect.SHOW_LISTENING in fx


def test_followup_expiry_and_rewake_without_chime() -> None:
    s, fx = next_state(State.FOLLOW_UP, Event.FOLLOWUP_TIMEOUT)
    assert s is State.IDLE and fx == ()
    s, fx = next_state(State.FOLLOW_UP, Event.SPEECH_START)
    assert s is State.LISTENING
    assert Effect.CHIME not in fx  # follow-up: no chime
    s, fx = next_state(State.FOLLOW_UP, Event.WAKE)
    assert Effect.CHIME in fx  # fresh wake: chime


def test_dictation_entry_and_exit() -> None:
    s, fx = next_state(State.IDLE, Event.DICTATION_START)
    assert s is State.DICTATING and Effect.SHOW_DICTATING in fx
    s, fx = next_state(s, Event.DICTATION_STOP)
    assert s is State.IDLE
    assert Effect.STOP_DICTATION in fx and Effect.HIDE_OVERLAY in fx


def test_mute_pause_resume() -> None:
    s, _ = next_state(State.IDLE, Event.MUTE)
    assert s is State.MUTED
    s, _ = next_state(s, Event.UNMUTE)
    assert s is State.IDLE
    s, _ = next_state(State.IDLE, Event.PAUSE)
    assert s is State.PAUSED
    s, _ = next_state(s, Event.RESUME)
    assert s is State.IDLE
    # mute from listening hides the overlay
    _, fx = next_state(State.LISTENING, Event.MUTE)
    assert Effect.HIDE_OVERLAY in fx


def test_cancel_while_listening() -> None:
    s, fx = next_state(State.LISTENING, Event.CANCEL)
    assert s is State.IDLE and Effect.HIDE_OVERLAY in fx


def test_pure_no_side_effects() -> None:
    """Calling next_state repeatedly must give identical results (purity)."""
    a = next_state(State.IDLE, Event.WAKE)
    b = next_state(State.IDLE, Event.WAKE)
    assert a == b
    assert next_state(State.IDLE, Event.WAKE)[0] is State.LISTENING  # state not mutated
