"""Renderer contract for DDT screens.

A DDT engine walks the XML database, issues ECU requests, and streams
results to whatever is showing the user a screen. That "whatever" is a
DDTRenderer. Implementations:

  - TkDDTRenderer  — adapter around the existing mod_ddt_screen.py
                     Tkinter code (desktop/Android).
  - WebViewDDTRenderer — serializes calls to JSON messages for the
                         iOS WKWebView (see ios/src/pyren_ios/).

Renderers receive model objects (mod_ddt_model.DDTScreen, ...). They
send user actions back via callbacks registered by the engine.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from mod_ddt_model import (
    DDTCategory,
    DDTDTC,
    DDTLogEntry,
    DDTScreen,
    DDTValueUpdate,
)


class DDTRenderer(object):
    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self, ecu_name: str, title: str = "") -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def set_categories(self, categories: List[DDTCategory]) -> None:
        raise NotImplementedError

    def show_screen(self, screen: DDTScreen) -> None:
        raise NotImplementedError

    def update_values(self, updates: List[DDTValueUpdate]) -> None:
        raise NotImplementedError

    def add_log(self, entry: DDTLogEntry) -> None:
        raise NotImplementedError

    def show_dtcs(self, dtcs: List[DDTDTC]) -> None:
        raise NotImplementedError

    def set_status(self, text: str) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Event sinks (set by the engine; renderer invokes them on user
    # input)
    # ------------------------------------------------------------------
    on_screen_selected: Optional[Callable[[str], None]] = None
    on_button_pressed: Optional[Callable[[str], None]] = None
    on_value_submitted: Optional[Callable[[str, str], None]] = None
    on_exit: Optional[Callable[[], None]] = None


class NullDDTRenderer(DDTRenderer):
    """A do-nothing renderer — useful for unit tests and headless runs."""

    def open(self, ecu_name: str, title: str = "") -> None: pass
    def close(self) -> None: pass
    def set_categories(self, categories): pass
    def show_screen(self, screen): pass
    def update_values(self, updates): pass
    def add_log(self, entry): pass
    def show_dtcs(self, dtcs): pass
    def set_status(self, text: str) -> None: pass


class RecordingDDTRenderer(DDTRenderer):
    """Records every incoming call. Used by tests and the WebView layer
    to build a replayable event stream."""

    def __init__(self) -> None:
        self.events: List[tuple] = []

    def open(self, ecu_name: str, title: str = "") -> None:
        self.events.append(("open", ecu_name, title))

    def close(self) -> None:
        self.events.append(("close",))

    def set_categories(self, categories):
        self.events.append(("set_categories", list(categories)))

    def show_screen(self, screen):
        self.events.append(("show_screen", screen))

    def update_values(self, updates):
        self.events.append(("update_values", list(updates)))

    def add_log(self, entry):
        self.events.append(("add_log", entry))

    def show_dtcs(self, dtcs):
        self.events.append(("show_dtcs", list(dtcs)))

    def set_status(self, text: str) -> None:
        self.events.append(("set_status", text))
