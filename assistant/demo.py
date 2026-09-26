"""``python -m assistant --demo``: run the core with fakes and a text REPL.

Phase 0 acceptance (BUILD_PLAN section 9): type utterances, see intents and
results, no real audio and no real side effects.

Honesty note: the rule parser here is a *placeholder* covering a handful of
phrases so the pipeline can be exercised end to end. The real rule grammar,
PermissionGuard, ConfirmationManager, and skill set arrive in Phases 2-3; this
demo wires state machine + event bus + activity log + fakes only.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from assistant.core.activity import ActivityLog
from assistant.core.bus import EventBus, ResultReady, StateChanged
from assistant.core.state import Effect, Event, State, next_state
from assistant.nlu.schema import Intent
from assistant.skills.base import Context, Plan, Result, Risk, Skill
from tests.fakes import FakeLLM, FakeSearch, FakeTTS, FakeWindows

log = logging.getLogger(__name__)


# --- placeholder NLU (Phase 2 replaces this with the real rule grammar) -----

_PATTERNS: list[tuple[re.Pattern[str], str, dict[str, str]]] = [
    (re.compile(r"^(?:open|launch|start)\s+(?P<app>.+)$", re.I), "app.open", {}),
    (re.compile(r"^close\s+(?P<app>.+)$", re.I), "window.close", {}),
    (re.compile(r"^(?:what is|who is|how do i|why is|search for)\s+(?P<query>.+)$", re.I),
     "research.ask", {}),
    (re.compile(r"^(?:volume)\s+(?P<change>up|down)$", re.I), "system.volume", {}),
    (re.compile(r"^(?:shut down|shutdown)$", re.I), "system.power", {"action": "shutdown"}),
    (re.compile(r"^note:\s*(?P<text>.+)$", re.I), "notes.add", {}),
]


class DemoSkill(Skill):
    """One fake skill handling every demo intent."""

    name: str = "demo"
    intents: tuple[str, ...] = (
        "app.open", "window.close", "research.ask",
        "system.volume", "system.power", "notes.add",
    )
    risk: dict[str, Risk] = {
        "app.open": Risk.SAFE,
        "window.close": Risk.CAREFUL,
        "research.ask": Risk.SAFE,
        "system.volume": Risk.SAFE,
        "system.power": Risk.CONFIRM,
        "notes.add": Risk.SAFE,
    }

    def __init__(self, tts: FakeTTS, windows: FakeWindows, search: FakeSearch, llm: FakeLLM):
        self._tts = tts
        self._windows = windows
        self._search = search
        self._llm = llm
        self.notes: list[str] = []

    async def plan(self, intent: Intent, ctx: Context) -> Plan:
        risk = self.risk.get(intent.name, Risk.SAFE)
        if intent.name == "system.power":
            summary = "Shut down the PC in 60 seconds. Say yes or no."
        elif intent.name == "window.close":
            summary = f"Close {intent.slots.get('app', 'it')}."
        elif intent.name == "app.open":
            summary = f"Open {intent.slots.get('app', '')}."
        else:
            summary = intent.name
        return Plan(intent=intent, risk=risk, summary=summary)

    async def execute(self, plan: Plan, ctx: Context) -> Result:
        intent = plan.intent
        if intent.name == "app.open":
            app = str(intent.slots.get("app", ""))
            self._windows.launch(app)
            return Result(ok=True, speech=f"Opening {app}.")
        if intent.name == "window.close":
            app = str(intent.slots.get("app", ""))
            self._windows.close(app)
            return Result(ok=True, speech=f"Closing {app}.")
        if intent.name == "research.ask":
            query = str(intent.slots.get("query", ""))
            results = self._search.search(query)
            summary = self._llm.complete(f"Summarise for: {query}") or (
                results[0]["snippet"] if results else "I couldn't find anything."
            )
            return Result(
                ok=True,
                speech=summary.split(".")[0][:80] + ".",
                display=summary,
                data={"top_result_url": results[0]["url"]} if results else None,
                left_pc=True,
            )
        if intent.name == "system.volume":
            return Result(ok=True, speech="Volume changed.")
        if intent.name == "system.power":
            return Result(ok=True, speech="Shutting down in 60 seconds.")
        if intent.name == "notes.add":
            text = str(intent.slots.get("text", ""))
            self.notes.append(text)
            return Result(ok=True, speech="Noted.")
        return Result(ok=False, speech="I can't do that yet.")


def parse(text: str) -> Intent | None:
    """Placeholder rule parser: first pattern wins, unknown text -> None."""
    text = text.strip()
    if not text:
        return None
    for pattern, name, fixed in _PATTERNS:
        m = pattern.match(text)
        if m:
            slots = {**fixed, **{k: v for k, v in m.groupdict().items() if v is not None}}
            return Intent(name=name, slots=slots, utterance=text, source="rules")
    return None


# --- minimal pipeline driver ------------------------------------------------

@dataclass
class DemoResult:
    state: State
    intent: Intent | None
    result: Result | None
    refused: bool = False
    cancelled: bool = False


class DemoPipeline:
    """Drives one utterance through state machine -> NLU -> plan -> (confirm) -> execute."""

    def __init__(
        self,
        tts: FakeTTS | None = None,
        windows: FakeWindows | None = None,
        search: FakeSearch | None = None,
        llm: FakeLLM | None = None,
        activity: ActivityLog | None = None,
        confirm: bool = True,
    ) -> None:
        self._pending: tuple[Intent, Plan, str] | None = None
        self.bus = EventBus()
        self.state = State.IDLE
        self.tts = tts or FakeTTS()
        self.windows = windows or FakeWindows()
        self.search = search or FakeSearch()
        self.llm = llm or FakeLLM()
        self.activity = activity
        self.skill = DemoSkill(self.tts, self.windows, self.search, self.llm)
        self.confirm = confirm
        self.transitions: list[tuple[State, State, tuple[Effect, ...]]] = []
        self.bus.subscribe(StateChanged, self._on_state)

    def _on_state(self, ev: StateChanged) -> None:
        self.transitions.append((ev.previous, ev.current, ev.effects))

    def _dispatch(self, event: Event) -> tuple[Effect, ...]:
        new_state, effects = next_state(self.state, event)
        if new_state != self.state or effects:
            prev = self.state
            self.state = new_state
            self.bus.publish(StateChanged(previous=prev, current=new_state, effects=effects))
        return effects

    async def handle(self, text: str) -> DemoResult:
        """Run one utterance through the full pipeline.

        If a confirmation is pending, ``text`` is taken as the yes/no answer
        (BUILD_PLAN section 6.5) and no new wake cycle is started.
        """
        if self.state is State.CONFIRMING:
            return await self._answer(text)

        self._dispatch(Event.WAKE)
        self._dispatch(Event.SPEECH_START)
        self._dispatch(Event.SPEECH_END)

        intent = parse(text)
        if intent is None:
            self._dispatch(Event.TRANSCRIPT_EMPTY)
            self.tts.speak("Sorry, I didn't get that.")
            self._dispatch(Event.RESPONSE_DONE)
            self._log(text, "unknown", "not understood", ok=False, left_pc=False)
            return DemoResult(state=self.state, intent=None, result=None)

        self._dispatch(Event.TRANSCRIPT_READY)

        ctx = Context(utterance=text)
        plan = await self.skill.plan(intent, ctx)

        if plan.risk is Risk.FORBIDDEN:
            self._dispatch(Event.INTENT_FORBIDDEN)
            self.tts.speak("I can't do that.")
            self._dispatch(Event.RESPONSE_DONE)
            self._log(text, intent.name, "forbidden", ok=False, left_pc=False)
            return DemoResult(state=self.state, intent=intent, result=None, refused=True)

        if plan.risk is Risk.CONFIRM and self.confirm:
            self._pending = (intent, plan, text)
            self._dispatch(Event.CONFIRM_NEEDED)
            # Stay in CONFIRMING; the REPL prints plan.summary and asks for yes/no.
            return DemoResult(state=self.state, intent=intent, result=None)

        self._dispatch(Event.INTENT_READY)

        return await self._execute(intent, plan, text)

    async def _answer(self, text: str) -> DemoResult:
        """Handle a yes/no reply while in CONFIRMING (section 6.5)."""
        pending = self._pending
        if pending is None:
            return DemoResult(state=self.state, intent=None, result=None)
        intent, plan, utterance = pending
        yes = text.strip().lower() in {
            "yes", "yeah", "confirm", "do it", "send it", "go ahead"
        }
        if not yes:
            self._pending = None
            self._dispatch(Event.CONFIRM_NO)
            self.tts.speak("Cancelled.")
            self._dispatch(Event.RESPONSE_DONE)
            self._log(utterance, intent.name, "cancelled", ok=False, left_pc=False)
            return DemoResult(state=self.state, intent=intent, result=None, cancelled=True)
        self._pending = None
        self._dispatch(Event.CONFIRM_YES)
        return await self._execute(intent, plan, utterance)

    async def _execute(self, intent: Intent, plan: Plan, text: str) -> DemoResult:
        ctx = Context(utterance=text)
        result = await self.skill.execute(plan, ctx)
        self._dispatch(Event.EXEC_DONE)
        self.tts.speak(result.speech)
        self.bus.publish(ResultReady(speech=result.speech, ok=result.ok,
                                      display=result.display, left_pc=result.left_pc))
        self._dispatch(Event.RESPONSE_DONE)
        self._log(text, intent.name, result.speech, ok=result.ok, left_pc=result.left_pc)
        return DemoResult(state=self.state, intent=intent, result=result)

    def _log(self, utterance: str, intent: str, result: str, ok: bool, left_pc: bool) -> None:
        if self.activity is not None:
            self.activity.record(utterance, intent, result, ok, left_pc)


def repl() -> None:
    """Interactive text REPL for ``--demo``."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        pipeline = DemoPipeline(activity=ActivityLog(Path(tmp) / "activity.db"))
        print("PC Assistant demo (Phase 0). Type an utterance, or 'quit'.")
        print("Try: open chrome | what is quantum tunnelling | shut down | blah blah")
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip().lower() in {"quit", "exit"}:
                break
            asyncio.run(_run_once(pipeline, line))
        print("Bye.")


async def _run_once(pipeline: DemoPipeline, line: str) -> None:
    result = await pipeline.handle(line.strip())
    _report(pipeline, result)


def _report(pipeline: DemoPipeline, res: DemoResult) -> None:
    if res.intent is not None:
        src = res.intent.source
        slots = ", ".join(f"{k}={v!r}" for k, v in res.intent.slots.items())
        print(f"  intent: {res.intent.name} ({slots}) [source={src}]")
    if res.cancelled:
        print("  result: cancelled")
    elif res.refused:
        print("  result: refused")
    elif res.state is State.CONFIRMING and res.result is None:
        pending = pipeline._pending
        summary = pending[1].summary if pending else "Confirm?"
        print(f"  confirm: {summary}")
    else:
        if res.result is not None:
            print(f"  speech: {res.result.speech}")
            if res.result.display:
                print(f"  overlay: {res.result.display}")
        elif pipeline.tts.last:
            print(f"  speech: {pipeline.tts.last}")
    print(f"  state: {res.state.value}")
