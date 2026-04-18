"""Toga implementation of the pyren UIBackend.

Pyren's diagnostic logic is synchronous and blocking: it runs on a
background worker thread and calls UIBackend methods (ask, choose,
writeln, ...) whenever it needs to interact with the user. Toga is
reactive and single-threaded on the main (UI) thread.

This backend bridges the two:

- Output methods (clear, write, writeln) are invoked from the worker
  thread. We schedule the UI mutation on the main thread via
  `app.loop.call_soon_threadsafe` and return immediately.

- Input methods (ask, choose, choose_long, choose_from_dict) block the
  worker thread on a `threading.Event`. The main thread renders the
  prompt, waits for the user's action, posts the answer into a shared
  slot, and sets the event. The worker resumes.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# Pyren core imports — the pyren3 directory is on sys.path (see app.py).
import mod_globals
from mod_ui import UIBackend


class TogaUIBackend(UIBackend):
    def __init__(self, app):
        self._app = app
        # Shared slot for the worker thread's pending answer.
        self._answer: Any = None
        self._answer_event = threading.Event()

    # ------------------------------------------------------------------
    # Main-thread helpers
    # ------------------------------------------------------------------
    def _on_main(self, fn, *args, **kwargs):
        """Schedule `fn(*args, **kwargs)` on the Toga event loop."""
        self._app.loop.call_soon_threadsafe(lambda: fn(*args, **kwargs))

    def _deliver_answer(self, value: Any) -> None:
        """Called from the main thread when the user has made a choice."""
        self._answer = value
        self._answer_event.set()

    def _wait_for_answer(self) -> Any:
        """Block the worker thread until the main thread delivers an answer."""
        self._answer_event.wait()
        value = self._answer
        self._answer = None
        self._answer_event.clear()
        return value

    # ------------------------------------------------------------------
    # UIBackend — output
    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._on_main(self._app.ui_clear_log)

    def write(self, text: str) -> None:
        self._on_main(self._app.ui_append_log, text)

    def writeln(self, text: str = "") -> None:
        self._on_main(self._app.ui_append_log, text + "\n")

    # ------------------------------------------------------------------
    # UIBackend — input
    # ------------------------------------------------------------------
    def ask(self, prompt: str = "") -> str:
        self._on_main(self._app.ui_prompt_text, prompt, self._deliver_answer)
        return self._wait_for_answer()

    def choose(self, items: List[str], question: str) -> List[str]:
        self._on_main(self._app.ui_prompt_choice, items, question, self._deliver_answer)
        key = self._wait_for_answer()
        # Match the legacy contract: [selected_item, key_string].
        if key == "Q":
            for s in items:
                if s.lower() in ("<up>", "<exit>"):
                    return [s, "Q"]
            return [items[-1], "Q"]
        idx = int(key) - 1
        return [items[idx], key]

    def choose_long(self, items: List[str], question: str, header: str = "") -> List[str]:
        # For MVP the iOS picker does not need pagination: a scrollable
        # list handles long option sets natively.
        return self.choose(items, question)

    def choose_from_dict(self, mapping: Dict[str, str], question: str, show_id: bool = True) -> List[str]:
        keys = sorted(mapping.keys())
        labels: List[str] = []
        for k in keys:
            if k.lower() in ("<up>", "<exit>"):
                labels.append(mapping[k])
            else:
                labels.append(f"({k}) {mapping[k]}" if show_id else mapping[k])
        self._on_main(self._app.ui_prompt_choice, labels, question, self._deliver_answer)
        key = self._wait_for_answer()
        if key == "Q":
            for k in keys:
                if k.lower() in ("<up>", "<exit>"):
                    return [k, "Q"]
            return [keys[-1], "Q"]
        idx = int(key) - 1
        return [keys[idx], key]
