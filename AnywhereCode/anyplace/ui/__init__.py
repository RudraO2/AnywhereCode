"""Anywhere Code UI toolkit: a phone-first TUI built on plain ``rich``.

Three layers, importable independently:

``anyplace.ui.layout``
    Terminal capability + breakpoint detection. Pure stdlib.
``anyplace.ui.theme``
    Style tokens and icon glyphs, each with an ASCII fallback.
``anyplace.ui.components`` / ``anyplace.ui.prompts``
    Rendering primitives and interview-grade input, all width-safe from 30 to
    120 columns and all headlessly testable.

Typical use::

    from rich.console import Console
    from anyplace import ui

    console = Console(width=ui.terminal_size()[0])
    ui.banner(console, subtitle="ship from your phone")
    ui.card(console, "Nothing to do yet.", title="Status", tone="info")
"""

from __future__ import annotations

from anyplace.ui.components import (
    MenuItem,
    banner,
    card,
    data_table,
    hint_bar,
    kv,
    menu,
    progress_line,
    rule,
    steps,
    truncate,
    wrap,
)
from anyplace.ui.layout import (
    LG,
    MD,
    SM,
    XS,
    Layout,
    breakpoint_for,
    content_width,
    is_narrow,
    is_termux,
    supports_color,
    supports_emoji,
    supports_unicode,
    terminal_size,
)
from anyplace.ui.prompts import (
    Choice,
    GoBack,
    InputFn,
    PromptAbort,
    QuitApp,
    ask_choice,
    ask_multi,
    ask_text,
    ask_yes_no,
    confirm_danger,
    pause,
    scripted_input,
)
from anyplace.ui.theme import ICONS, THEMES, Theme, get_theme

__all__ = [
    # layout
    "XS",
    "SM",
    "MD",
    "LG",
    "Layout",
    "terminal_size",
    "breakpoint_for",
    "is_narrow",
    "is_termux",
    "supports_unicode",
    "supports_emoji",
    "supports_color",
    "content_width",
    # theme
    "ICONS",
    "THEMES",
    "Theme",
    "get_theme",
    # components
    "MenuItem",
    "banner",
    "card",
    "menu",
    "kv",
    "data_table",
    "steps",
    "hint_bar",
    "rule",
    "progress_line",
    "wrap",
    "truncate",
    # prompts
    "PromptAbort",
    "GoBack",
    "QuitApp",
    "Choice",
    "InputFn",
    "scripted_input",
    "ask_choice",
    "ask_text",
    "ask_yes_no",
    "ask_multi",
    "confirm_danger",
    "pause",
]
