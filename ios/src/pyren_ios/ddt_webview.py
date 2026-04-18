"""WebView-backed DDTRenderer for iOS.

Serializes every renderer call to a JSON message and hands it to a
JavaScript function (window.pyrenReceive) running inside a Toga WebView
(which is WKWebView on iOS). User actions bubble back through a message
handler registered by the Toga app.

Threading:
  Renderer methods are called from the pyren worker thread. DOM updates
  must happen on the main thread, so every call is scheduled via
  `app.loop.call_soon_threadsafe`. User-action callbacks run on the main
  thread and hand off to the engine-supplied event sinks.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable, List, Optional

import mod_ddt_model as mdl
from mod_ddt_renderer import DDTRenderer


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    return obj


class WebViewDDTRenderer(DDTRenderer):
    def __init__(self, app, webview) -> None:
        self._app = app
        self._webview = webview

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _send(self, kind: str, **payload: Any) -> None:
        msg = {"kind": kind, **payload}
        js = "window.pyrenReceive(%s);" % json.dumps(msg, ensure_ascii=False)
        self._app.loop.call_soon_threadsafe(self._eval, js)

    def _eval(self, js: str) -> None:
        # Toga exposes evaluate_javascript on WebView.
        try:
            self._webview.evaluate_javascript(js)
        except Exception as exc:  # noqa: BLE001
            # The app log is still useful if the bridge call fails.
            try:
                self._app.ui_append_log("DDT bridge error: %r\n" % exc)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Inbound user events (called by the Toga app on the main thread)
    # ------------------------------------------------------------------
    def handle_incoming(self, msg: Any) -> None:
        if isinstance(msg, str):
            try:
                msg = json.loads(msg)
            except Exception:
                return
        if not isinstance(msg, dict):
            return
        kind = msg.get("kind")
        if kind == "select_screen" and self.on_screen_selected:
            self.on_screen_selected(msg.get("name", ""))
        elif kind == "button_pressed" and self.on_button_pressed:
            self.on_button_pressed(msg.get("id", ""))
        elif kind == "value_submitted" and self.on_value_submitted:
            self.on_value_submitted(msg.get("id", ""), msg.get("value", ""))
        elif kind == "ready":
            # First handshake from the WebView — no action needed yet.
            pass

    # ------------------------------------------------------------------
    # DDTRenderer implementation
    # ------------------------------------------------------------------
    def open(self, ecu_name: str, title: str = "") -> None:
        self._send("open", ecu_name=ecu_name, title=title)

    def close(self) -> None:
        self._send("close")

    def set_categories(self, categories: List[mdl.DDTCategory]) -> None:
        self._send("set_categories", categories=_serialize(list(categories)))

    def show_screen(self, screen: mdl.DDTScreen) -> None:
        self._send("show_screen", screen=_serialize(screen))

    def update_values(self, updates: List[mdl.DDTValueUpdate]) -> None:
        self._send("update_values", updates=_serialize(list(updates)))

    def add_log(self, entry: mdl.DDTLogEntry) -> None:
        self._send("add_log", entry=_serialize(entry))

    def show_dtcs(self, dtcs: List[mdl.DDTDTC]) -> None:
        self._send("show_dtcs", dtcs=_serialize(list(dtcs)))

    def set_status(self, text: str) -> None:
        self._send("set_status", text=text)
