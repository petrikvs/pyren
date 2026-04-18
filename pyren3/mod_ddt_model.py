"""Pure-data model for DDT screens.

DDT (Diag Downloading Tool) screens are defined as XML in the Renault
diagnostic database and rendered live against an ECU. Historically the
only renderer was Tkinter (see mod_ddt_screen.py). For the iOS port we
need a renderer that talks to a WKWebView, so this module defines the
minimum data types that both a Tk renderer and a WebView renderer can
consume.

The model is intentionally a thin, JSON-friendly mirror of the XML
schema — not a full UI tree. A renderer is free to lay out widgets
however the target platform prefers (native Tk widgets, HTML elements,
native iOS controls, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class DDTCategory:
    """Top-level grouping of screens for an ECU (e.g. "Identifications")."""
    name: str
    screens: List[str] = field(default_factory=list)  # screen names in order


@dataclass
class DDTWidget:
    """One visible element on a screen.

    `kind` mirrors the XML tag so any renderer can dispatch:
        "label", "display", "input", "button", "list", "text", "image"
    `props` carries kind-specific attributes (text, binding, options...).
    """
    kind: str
    id: str = ""
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DDTScreen:
    """A full screen: layout of widgets plus the requests it fires."""
    name: str
    widgets: List[DDTWidget] = field(default_factory=list)
    # Data bindings: map DataName -> initial request spec so the engine
    # knows what to poll while the screen is live.
    data_refs: List[str] = field(default_factory=list)
    # Requests issued when the screen becomes active (order matters).
    start_requests: List[str] = field(default_factory=list)


@dataclass
class DDTValueUpdate:
    """One field's value change, pushed to the renderer during polling."""
    data_name: str
    value: str
    color: Optional[str] = None  # e.g. "red" for out-of-range


@dataclass
class DDTLogEntry:
    """A raw request/response pair for the log view."""
    timestamp: str
    direction: str  # ">" for sent, "<" for received
    text: str


@dataclass
class DDTDTC:
    """One Diagnostic Trouble Code entry."""
    code: str
    description: str
    status: str = ""


def to_json(obj: Any) -> Dict[str, Any]:
    """Best-effort conversion of any dataclass in this module to a dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_json(x) for x in obj]
    return obj
