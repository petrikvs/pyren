"""Toga application shell for pyren on iOS.

Flow:
  1. User sees a Connect screen with IP:port input (default 192.168.0.10:35000).
  2. Tapping Connect spawns a worker thread that:
       - sets the required mod_globals.opt_* fields,
       - installs the Toga UIBackend and stdio capture,
       - calls pyren3.run_interactive().
  3. All subsequent print()/input()/Choice() calls from pyren are
     routed to the Toga UI via TogaUIBackend.

This MVP renders the session as a log view plus an overlay for prompts
and choice pickers. Richer dedicated screens (ECU list, DTC view, etc.)
are a later refinement — they can replace log output once the backend
exposes structured events.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW


def _bootstrap_pyren_path() -> None:
    """Ensure pyren3 sources are importable.

    Briefcase bundles ../pyren3 alongside the pyren_ios package inside
    the app resources. We resolve that directory at runtime and prepend
    it to sys.path.
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "pyren3",           # when bundled flat next to pyren_ios
        here.parent.parent / "pyren3",    # dev layout (repo/ios/src/.. -> repo/pyren3)
    ]
    for cand in candidates:
        if cand.is_dir():
            sys.path.insert(0, str(cand))
            os.chdir(str(cand))
            return
    raise RuntimeError("pyren3 sources not found in bundle")


class PyRenApp(toga.App):
    # ------------------------------------------------------------------
    # Toga lifecycle
    # ------------------------------------------------------------------
    def startup(self) -> None:
        self._worker: threading.Thread | None = None
        self._pending_answer_cb = None

        self._log = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, padding=4),
        )
        self._port_input = toga.TextInput(
            placeholder="192.168.0.10:35000",
            value="192.168.0.10:35000",
            style=Pack(flex=1, padding=4),
        )
        self._connect_btn = toga.Button(
            "Connect",
            on_press=self._on_connect_pressed,
            style=Pack(padding=4),
        )
        self._status_label = toga.Label(
            "Ready",
            style=Pack(padding=4),
        )

        # Prompt row (hidden until pyren asks for input).
        self._prompt_label = toga.Label("", style=Pack(padding=4))
        self._prompt_input = toga.TextInput(style=Pack(flex=1, padding=4))
        self._prompt_submit = toga.Button(
            "Submit",
            on_press=self._on_prompt_submit,
            style=Pack(padding=4),
        )
        self._prompt_box = toga.Box(
            children=[self._prompt_label, self._prompt_input, self._prompt_submit],
            style=Pack(direction=ROW, padding=4),
        )
        self._prompt_box.enabled = False

        header = toga.Box(
            children=[self._port_input, self._connect_btn],
            style=Pack(direction=ROW),
        )
        root = toga.Box(
            children=[header, self._status_label, self._log, self._prompt_box],
            style=Pack(direction=COLUMN),
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = root
        self.main_window.show()

    # ------------------------------------------------------------------
    # UI helpers called from the Toga backend (always on main thread)
    # ------------------------------------------------------------------
    def ui_append_log(self, text: str) -> None:
        self._log.value = (self._log.value or "") + text

    def ui_clear_log(self) -> None:
        self._log.value = ""

    def ui_prompt_text(self, prompt: str, answer_cb) -> None:
        self._pending_answer_cb = answer_cb
        self._prompt_label.text = prompt or "Input:"
        self._prompt_input.value = ""
        self._prompt_box.enabled = True
        self._prompt_input.focus()

    def ui_prompt_choice(self, items, question: str, answer_cb) -> None:
        """Render a choice picker using a dialog with indexed buttons.

        For MVP we post the menu into the log and reuse the text prompt
        for the user's numeric answer — this preserves the original
        pyren contract without requiring a native picker widget.
        """
        lines = [f"{question}"]
        for i, s in enumerate(items, 1):
            key = "Q" if s.lower() in ("<up>", "<exit>") else str(i)
            lines.append(f"  {key} - {s}")
        self.ui_append_log("\n".join(lines) + "\n")
        self.ui_prompt_text(question, answer_cb)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_connect_pressed(self, widget) -> None:
        if self._worker and self._worker.is_alive():
            return
        port = (self._port_input.value or "").strip()
        if not port:
            self._status_label.text = "Enter an IP:port first."
            return

        self._connect_btn.enabled = False
        self._status_label.text = f"Connecting to {port}..."
        self._log.value = ""

        self._worker = threading.Thread(
            target=self._run_session,
            args=(port,),
            daemon=True,
        )
        self._worker.start()

    def _on_prompt_submit(self, widget) -> None:
        if self._pending_answer_cb is None:
            return
        cb, self._pending_answer_cb = self._pending_answer_cb, None
        answer = self._prompt_input.value or ""
        self._prompt_box.enabled = False
        self._prompt_label.text = ""
        self._prompt_input.value = ""
        cb(answer)

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------
    def _run_session(self, port: str) -> None:
        _bootstrap_pyren_path()

        # Import inside the worker so the worker thread owns the pyren
        # modules' import-time side effects (chdir, etc.).
        import mod_globals
        import mod_ui
        from pyren_ios.toga_backend import TogaUIBackend

        backend = TogaUIBackend(self)
        mod_globals.ui = backend
        mod_ui.install_stdio_capture(backend)

        mod_globals.os = "ios"
        mod_globals.opt_port = port
        mod_globals.opt_speed = 38400
        mod_globals.opt_rate = 38400
        mod_globals.opt_lang = "GB"
        mod_globals.opt_log = ""
        mod_globals.opt_demo = False
        mod_globals.opt_scan = False
        mod_globals.opt_car = ""
        mod_globals.opt_ecuid = ""
        mod_globals.opt_csv = False
        mod_globals.opt_csv_only = False
        mod_globals.opt_csv_human = False
        mod_globals.opt_usrkey = ""
        mod_globals.opt_verbose = False
        mod_globals.opt_si = False
        mod_globals.opt_cfc0 = False
        mod_globals.opt_caf = False
        mod_globals.opt_n1c = False
        mod_globals.opt_exp = False
        mod_globals.opt_dump = False
        mod_globals.opt_can2 = False
        mod_globals.opt_performance = False
        mod_globals.opt_sd = False
        mod_globals.opt_minordtc = False
        mod_globals.opt_excel = False
        mod_globals.opt_dev = False
        mod_globals.opt_devses = "1086"
        mod_globals.opt_csv_sep = ","
        mod_globals.opt_csv_dec = "."

        try:
            import pyren3
            pyren3.run_interactive()
        except SystemExit:
            backend.writeln("Session ended.")
        except Exception as exc:  # noqa: BLE001
            backend.writeln(f"ERROR: {exc!r}")
        finally:
            mod_ui.uninstall_stdio_capture()
            self.loop.call_soon_threadsafe(self._on_session_finished)

    def _on_session_finished(self) -> None:
        self._connect_btn.enabled = True
        self._status_label.text = "Disconnected."


def main():
    return PyRenApp(
        formal_name="PyRen",
        app_id="com.github.petrikvs.pyren_ios",
    )
