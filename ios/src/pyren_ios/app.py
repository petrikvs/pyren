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

# iOS simulator/device returns a locale string Python's locale module
# cannot resolve; Toga unconditionally calls locale.setlocale(LC_ALL, "")
# in App.__init__, which raises locale.Error and kills the app before
# startup(). Patch here (before toga is imported) so it falls back to C.
import locale as _locale

os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")

_orig_setlocale = _locale.setlocale


def _safe_setlocale(category, loc=None):
    try:
        return _orig_setlocale(category, loc)
    except _locale.Error:
        try:
            return _orig_setlocale(category, "C")
        except _locale.Error:
            return None


_locale.setlocale = _safe_setlocale

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from pyren_ios.db_manager import DatabaseManager


def _pyren3_source_dir() -> Path:
    """Locate the bundled pyren3 sources (read-only inside the .app)."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "pyren3",           # when bundled flat next to pyren_ios
        here.parent.parent / "pyren3",    # dev layout (repo/ios/src/.. -> repo/pyren3)
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand
    raise RuntimeError("pyren3 sources not found in bundle")


_README_TEXT = """\
Drop the following zips into this folder to install pyren's databases:

  * pyrendata_*.zip   — CLIP (Renault ECU database)
                        top-level entries: EcuRenault, Vehicles, Location, ...

  * DDT2000data_*.zip — DDT (Renault diagnostic screens)
                        top-level entries: ecus, graphics, images, vehicles

Alternate names are fine — the app auto-detects and renames on Rescan.

This file is safe to delete.
"""


def _work_dir() -> Path:
    """Writable working directory for pyren on iOS.

    The app bundle is read-only, so pyren can't write cache/ or logs/
    into its source tree. Documents is the standard writable location,
    and it's the one exposed to the Files app via UIFileSharingEnabled —
    users drop imported zips there.

    iOS only surfaces the app's Documents folder in the Files app after
    it contains at least one file, so we drop a short README on first
    launch to guarantee the folder shows up.

    We also pre-create every subdirectory pyren's chkDirTree() wants.
    On iOS, relative os.makedirs() calls from this path occasionally
    fail with EPERM (likely a /var vs /private/var canonicalization
    quirk in the sandbox check) — creating them here via absolute
    paths sidesteps that path entirely, and chkDirTree() then short-
    circuits on its os.path.exists() guards.
    """
    d = Path.home() / "Documents"
    d.mkdir(parents=True, exist_ok=True)
    for sub in ("cache", "csv", "logs", "dumps", "macro", "doc", "MTCSAVE"):
        (d / sub).mkdir(exist_ok=True)
    readme = d / "README.txt"
    if not readme.exists():
        try:
            readme.write_text(_README_TEXT, encoding="utf-8")
        except OSError:
            pass
    return d


def _bootstrap_pyren_path() -> None:
    """Put pyren3 on sys.path and chdir into the writable work dir.

    pyren uses relative paths everywhere (cache/, logs/, pyrendata*.zip),
    so the cwd *is* the pyren data directory.
    """
    sys.path.insert(0, str(_pyren3_source_dir()))
    os.chdir(str(_work_dir()))


def _trigger_local_network_permission() -> None:
    """Force iOS to show the Local Network permission prompt.

    iOS 14+ requires user consent for any LAN traffic. A plain
    socket.connect() to a LAN IP often fails silently with EPERM
    *without* showing the system prompt — Apple's heuristics only
    trigger it for Bonjour/mDNS-style discovery traffic. Sending a
    UDP broadcast is enough to flip the switch: iOS sees the packet,
    raises the prompt, and once the user accepts, subsequent TCP
    connects to LAN peers succeed.

    Safe to call repeatedly; does nothing once permission is granted
    (or denied). Errors are swallowed — this is a best-effort nudge.
    """
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.settimeout(0.5)
            s.sendto(b"\x00", ("255.255.255.255", 1))
        finally:
            s.close()
    except OSError:
        pass


class PyRenApp(toga.App):
    # ------------------------------------------------------------------
    # Toga lifecycle
    # ------------------------------------------------------------------
    def startup(self) -> None:
        self._worker: threading.Thread | None = None
        self._pending_answer_cb = None
        self._ddt_renderer = None
        self._ddt_poll_handle = None
        self._db_manager = DatabaseManager(_work_dir())

        # --- Databases panel --------------------------------------------
        self._clip_status = toga.Label("CLIP: —", style=Pack(padding=4))
        self._ddt_status = toga.Label("DDT: —", style=Pack(padding=4))
        self._import_clip_btn = toga.Button(
            "Import CLIP",
            on_press=self._on_import_clip,
            style=Pack(flex=1, padding=4),
        )
        self._import_ddt_btn = toga.Button(
            "Import DDT",
            on_press=self._on_import_ddt,
            style=Pack(flex=1, padding=4),
        )
        self._rescan_btn = toga.Button(
            "Rescan",
            on_press=self._on_rescan_pressed,
            style=Pack(flex=1, padding=4),
        )
        db_buttons = toga.Box(
            children=[self._import_clip_btn, self._import_ddt_btn, self._rescan_btn],
            style=Pack(direction=ROW),
        )
        db_panel = toga.Box(
            children=[self._clip_status, self._ddt_status, db_buttons],
            style=Pack(direction=COLUMN),
        )
        self._refresh_db_status()

        # --- Session tab -------------------------------------------------
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
        session_tab = toga.Box(
            children=[db_panel, header, self._status_label, self._log, self._prompt_box],
            style=Pack(direction=COLUMN),
        )

        # --- DDT tab (WebView) ------------------------------------------
        # iOS Toga WebView only accepts http(s) URLs, not file://. Load the
        # bundled HTML via set_content() instead — root_url is just the base
        # for relative resource URLs, which we don't use (everything is inline).
        self._ddt_webview = toga.WebView(style=Pack(flex=1))
        ddt_html_path = Path(__file__).resolve().parent / "web" / "ddt.html"
        if ddt_html_path.exists():
            self._ddt_webview.set_content(
                "https://pyren.local/",
                ddt_html_path.read_text(encoding="utf-8"),
            )
        ddt_tab = toga.Box(
            children=[self._ddt_webview],
            style=Pack(direction=COLUMN),
        )

        # Tabbed container — iOS renders this as a UITabBar.
        self._tabs = toga.OptionContainer(
            content=[
                ("Session", session_tab),
                ("DDT", ddt_tab),
            ],
            style=Pack(flex=1),
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self._tabs
        self.main_window.show()

        # Nudge iOS into showing the Local Network permission prompt
        # up front, so TCP connect to the ELM adapter isn't blocked by
        # EPERM later. See _trigger_local_network_permission() for why.
        _trigger_local_network_permission()

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
    # Database import handlers
    # ------------------------------------------------------------------
    def _refresh_db_status(self) -> None:
        st = self._db_manager.scan()
        if st.clip is not None:
            size_mb = st.clip.stat().st_size / (1024 * 1024)
            self._clip_status.text = f"CLIP: {st.clip.name} ({size_mb:.1f} MB)"
        else:
            self._clip_status.text = "CLIP: (not imported)"
        if st.ddt is not None:
            size_mb = st.ddt.stat().st_size / (1024 * 1024)
            self._ddt_status.text = f"DDT: {st.ddt.name} ({size_mb:.1f} MB)"
        else:
            self._ddt_status.text = "DDT: (not imported)"

    def _on_rescan_pressed(self, widget) -> None:
        # Adopt anything the user dropped into Documents via the Files app.
        adopted = self._db_manager.auto_classify_pending()
        for final, kind in adopted:
            self.ui_append_log(f"Imported {kind.upper()}: {final.name}\n")
        self._refresh_db_status()

    async def _on_import_clip(self, widget) -> None:
        await self._show_import_instructions("CLIP", "pyrendata")

    async def _on_import_ddt(self, widget) -> None:
        await self._show_import_instructions("DDT", "DDT2000data")

    async def _show_import_instructions(self, label: str, prefix: str) -> None:
        """iOS Toga doesn't implement OpenFileDialog, so importing a
        database on-device means dropping the zip into the app's
        Documents folder via the iOS Files app (AirDrop, Share Sheet,
        iCloud Drive, Save to Files...). We auto-classify and rename
        zips on Rescan so the user doesn't have to rename them.
        """
        # Opportunistic rescan first — maybe they already dropped the file.
        self._on_rescan_pressed(None)
        await self.main_window.dialog(
            toga.InfoDialog(
                f"Import {label} database",
                (
                    "iOS doesn't let apps open a file picker outside their "
                    "sandbox, so imports go through the Files app:\n\n"
                    "1. Open the Files app.\n"
                    "2. Navigate to 'On My iPhone › PyRen'.\n"
                    "3. Drop the zip there (AirDrop, Share Sheet, or "
                    "'Save to Files').\n"
                    "4. Come back and tap Rescan.\n\n"
                    f"PyRen will auto-detect the zip's contents and rename "
                    f"it to {prefix}_*.zip so the engine picks it up."
                ),
            )
        )

    # ------------------------------------------------------------------
    # DDT WebView bridge (JS <-> Python)
    # ------------------------------------------------------------------
    def _ddt_inject_bridge_js(self) -> None:
        """Replace window.webkit.messageHandlers.pyren with an in-page
        queue that Python drains via evaluate_javascript polling.

        Toga's WebView doesn't yet expose a cross-platform native message
        handler API, so we funnel every outbound JS action into
        window._pyrenOutbox[] and have the host pull from it.
        """
        js = (
            "window._pyrenOutbox = window._pyrenOutbox || [];"
            "if (!window.webkit) { window.webkit = {}; }"
            "window.webkit.messageHandlers = window.webkit.messageHandlers || {};"
            "window.webkit.messageHandlers.pyren = {"
            "  postMessage: function(m){ window._pyrenOutbox.push(JSON.stringify(m)); }"
            "};"
        )
        try:
            self._ddt_webview.evaluate_javascript(js)
        except Exception:
            pass

    def _ddt_poll_outbox(self) -> None:
        """Drain the JS outbox and dispatch messages to the renderer."""
        if self._ddt_renderer is None:
            return
        js = (
            "(function(){var q=window._pyrenOutbox||[];"
            "window._pyrenOutbox=[];return JSON.stringify(q);})()"
        )

        def on_result(value):
            try:
                import json
                arr = json.loads(value) if value else []
                for raw in arr:
                    self._ddt_renderer.handle_incoming(raw)
            except Exception:
                pass

        try:
            self._ddt_webview.evaluate_javascript(js, on_result=on_result)
        except TypeError:
            # Older Toga versions: evaluate_javascript(js) only, no callback.
            try:
                self._ddt_webview.evaluate_javascript(js)
            except Exception:
                pass
        except Exception:
            pass

        # Reschedule at ~5 Hz — fast enough for taps, cheap enough to idle.
        self._ddt_poll_handle = self.loop.call_later(0.2, self._ddt_poll_outbox)

    def _ddt_start_polling(self) -> None:
        if self._ddt_poll_handle is None:
            self._ddt_inject_bridge_js()
            self._ddt_poll_outbox()

    def _ddt_stop_polling(self) -> None:
        if self._ddt_poll_handle is not None:
            self._ddt_poll_handle.cancel()
            self._ddt_poll_handle = None

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------
    def _run_session(self, port: str) -> None:
        _bootstrap_pyren_path()
        # Safety net: re-trigger the Local Network prompt in case the
        # user hadn't seen/handled it yet by the time they pressed Connect.
        _trigger_local_network_permission()

        # Import inside the worker so the worker thread owns the pyren
        # modules' import-time side effects (chdir, etc.).
        import mod_globals
        import mod_ui
        from pyren_ios.toga_backend import TogaUIBackend
        from pyren_ios.ddt_webview import WebViewDDTRenderer

        backend = TogaUIBackend(self)
        mod_globals.ui = backend
        mod_ui.install_stdio_capture(backend)

        # Build the WebView renderer on the worker side (safe: it only
        # schedules work on the main loop; it doesn't touch the widget
        # from this thread).
        self._ddt_renderer = WebViewDDTRenderer(self, self._ddt_webview)
        self.loop.call_soon_threadsafe(self._ddt_start_polling)

        mod_globals.os = "ios"
        # Point every pyren work-dir global at the pre-created absolute
        # paths under Documents. Relative './cache' makedirs intermittently
        # hit EPERM in the iOS sandbox even with cwd in Documents —
        # using absolute paths sidesteps that, and they survive cwd
        # changes made by sub-modules.
        _d = _work_dir()
        mod_globals.user_data_dir = str(_d) + "/"
        mod_globals.cache_dir = str(_d / "cache") + "/"
        mod_globals.csv_dir = str(_d / "csv") + "/"
        mod_globals.log_dir = str(_d / "logs") + "/"
        mod_globals.dumps_dir = str(_d / "dumps") + "/"
        mod_globals.macro_dir = str(_d / "macro") + "/"
        mod_globals.doc_dir = str(_d / "doc") + "/"
        mod_globals.mtcsave_dir = str(_d / "MTCSAVE")
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

        # Surface where pyren is running from + which DBs it can see, so a
        # PermissionError from a stray mkdir/open is traceable without a
        # device-side debugger.
        backend.writeln(f"cwd: {os.getcwd()}")
        try:
            import mod_db_manager as _dbm
            backend.writeln(f"DB dir scan: {sorted(p.name for p in self._db_manager.work_dir.glob('*.zip'))}")
        except Exception:
            pass

        try:
            import pyren3
            pyren3.run_interactive()
        except SystemExit:
            backend.writeln("Session ended.")
        except Exception as exc:  # noqa: BLE001
            import traceback
            backend.writeln(f"ERROR: {exc!r}")
            backend.writeln(traceback.format_exc())
        finally:
            mod_ui.uninstall_stdio_capture()
            self.loop.call_soon_threadsafe(self._on_session_finished)

    def _on_session_finished(self) -> None:
        self._connect_btn.enabled = True
        self._status_label.text = "Disconnected."
        self._ddt_stop_polling()
        self._ddt_renderer = None


def main():
    return PyRenApp(
        formal_name="PyRen",
        app_id="com.github.petrikvs.pyren_ios",
    )
