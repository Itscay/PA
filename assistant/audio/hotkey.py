"""Push-to-talk global hotkey (BUILD_PLAN section 1.3/4/9).

``pynput`` listener on a configurable combo (default Ctrl+Alt+Space). The
hotkey moves IDLE/FOLLOW_UP -> LISTENING, and interrupts TTS (barge-in) while
speech is playing.

Runs on its own thread; callbacks receive raw press/release events so the
orchestrator can distinguish hold-to-talk later if needed (v1: press = toggle
one utterance).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_HOTKEY = "ctrl+alt+space"

# pynput naming -> our parse
_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "cmd": "cmd",
    "super": "cmd",
    "win": "cmd",
}


def parse_hotkey(spec: str) -> frozenset[str]:
    """Parse 'ctrl+alt+space' -> {'ctrl', 'alt', 'space'} (normalized, sorted)."""
    keys = set()
    for part in spec.lower().split("+"):
        part = part.strip()
        if not part:
            raise ValueError(f"empty key in hotkey spec: {spec!r}")
        keys.add(_MODIFIER_ALIASES.get(part, part))
    if not keys:
        raise ValueError(f"empty hotkey spec: {spec!r}")
    return frozenset(keys)


class PushToTalk:
    """Listens for the hotkey combo; fires ``on_press`` from the input thread."""

    def __init__(
        self,
        on_press: Callable[[], None],
        spec: str = DEFAULT_HOTKEY,
        on_release: Callable[[], None] | None = None,
    ) -> None:
        self._keys = parse_hotkey(spec)
        self._on_press = on_press
        self._on_release = on_release
        self._spec = spec
        # pynput ships no stubs; listener is stopped in stop().
        self._listener: Any = None
        self._held: set[str] = set()
        self._lock = threading.Lock()
        self.pressed_count = 0
        self._combo_armed = False  # edge-trigger: one fire per combo press

    @property
    def active(self) -> bool:
        return self._listener is not None

    def _normalize(self, key: object) -> str | None:
        """Map pynput keys to our combo vocabulary.

        Real pynput events are side-specific and arrive in two flavors:
        left Ctrl -> ``Key.ctrl_l`` (name "ctrl_l"), and space can be either
        ``Key.space`` (name "space") or ``KeyCode.from_char(' ')`` (char
        " "). Without collapsing these, a ``ctrl+alt+space`` combo parsed
        from config would never match a real key press (verified against
        live events on Windows).
        """
        try:
            from pynput.keyboard import Key

            if isinstance(key, Key):
                name = (key.name or str(key).rsplit(".", 1)[-1]).lower()
                if name == "space":
                    return "space"
                for base in ("ctrl", "alt", "shift", "cmd"):
                    if name == base or name.startswith(base + "_"):
                        return base
                return name
            char = getattr(key, "char", None)
            if char == " ":
                return "space"
            return char
        except Exception:
            return None

    def _handle(self, key: object, pressed: bool) -> None:
        name = self._normalize(key)
        if name is None:
            return
        with self._lock:
            if pressed:
                self._held.add(name)
            else:
                self._held.discard(name)
            combo_held = self._keys <= self._held
            # Fire only on the transition into "combo complete"; extra keys
            # pressed while holding the combo must not re-fire it.
            fire_press = bool(pressed and combo_held and not self._combo_armed)
            self._combo_armed = combo_held
            fire_release = bool(
                not pressed and not self._held and self._on_release is not None
            )
        if fire_press:
            log.info("push-to-talk pressed (%s)", self._spec)
            self.pressed_count += 1
            self._on_press()
        if fire_release and self._on_release is not None:
            self._on_release()

    def start(self) -> None:
        from pynput import keyboard

        self._combo_armed = False
        self._held.clear()
        self._listener = keyboard.Listener(
            on_press=lambda k: self._handle(k, True),
            on_release=lambda k: self._handle(k, False),
        )
        self._listener.start()
        log.info("push-to-talk active: %s", self._spec)

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                log.exception("hotkey listener stop failed")
