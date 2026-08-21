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

from typing import TYPE_CHECKING

# Imports are lazy (PEP 562) so the promise at the top of this docstring --
# three layers, importable independently -- is actually true. `layout` is pure
# stdlib, and a pure-logic module that only needs the terminal width should not
# pay for `rich` to be imported. `anyplace.core.doctor` relies on this.
#
# Attribute access on the package still works exactly as before:
#     from anyplace import ui
#     ui.card(console, "hello")

_EXPORTS = {
    # layout (pure stdlib)
    "XS": "anyplace.ui.layout",
    "SM": "anyplace.ui.layout",
    "MD": "anyplace.ui.layout",
    "LG": "anyplace.ui.layout",
    "Layout": "anyplace.ui.layout",
    "terminal_size": "anyplace.ui.layout",
    "breakpoint_for": "anyplace.ui.layout",
    "is_narrow": "anyplace.ui.layout",
    "is_termux": "anyplace.ui.layout",
    "supports_unicode": "anyplace.ui.layout",
    "supports_emoji": "anyplace.ui.layout",
    "supports_color": "anyplace.ui.layout",
    "content_width": "anyplace.ui.layout",
    # theme
    "ICONS": "anyplace.ui.theme",
    "THEMES": "anyplace.ui.theme",
    "Theme": "anyplace.ui.theme",
    "get_theme": "anyplace.ui.theme",
    # components (pulls in rich)
    "MenuItem": "anyplace.ui.components",
    "banner": "anyplace.ui.components",
    "card": "anyplace.ui.components",
    "count_noun": "anyplace.ui.components",
    "menu": "anyplace.ui.components",
    "kv": "anyplace.ui.components",
    "data_table": "anyplace.ui.components",
    "steps": "anyplace.ui.components",
    "hint_bar": "anyplace.ui.components",
    "rule": "anyplace.ui.components",
    "progress_line": "anyplace.ui.components",
    "wrap": "anyplace.ui.components",
    "truncate": "anyplace.ui.components",
    # prompts
    "PromptAbort": "anyplace.ui.prompts",
    "GoBack": "anyplace.ui.prompts",
    "QuitApp": "anyplace.ui.prompts",
    "Choice": "anyplace.ui.prompts",
    "InputFn": "anyplace.ui.prompts",
    "scripted_input": "anyplace.ui.prompts",
    "ask_choice": "anyplace.ui.prompts",
    "ask_text": "anyplace.ui.prompts",
    "ask_yes_no": "anyplace.ui.prompts",
    "ask_multi": "anyplace.ui.prompts",
    "confirm_danger": "anyplace.ui.prompts",
    "pause": "anyplace.ui.prompts",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    """Resolve a re-exported name on first use (PEP 562)."""
    try:
        module_name = _EXPORTS[name]
    except KeyError:
        raise AttributeError("module %r has no attribute %r" % (__name__, name)) from None

    import importlib

    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value  # cache, so this runs once per name
    return value


def __dir__():
    return sorted(set(list(globals()) + __all__))


if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from anyplace.ui.components import (
        MenuItem,
        banner,
        card,
        count_noun,
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
