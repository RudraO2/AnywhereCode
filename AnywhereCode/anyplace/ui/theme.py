"""Colour tokens and icon glyphs for Anywhere Code.

Two rules drive everything here:

1. **Every icon has an ASCII fallback.** Termux fonts render a lot of emoji as
   tofu, and double-width glyphs quietly corrupt layout maths, so no signal is
   ever carried by an emoji alone.
2. **Every colour is a token, never a literal.** Components ask for
   ``theme.style("warn")``; the theme decides whether that is yellow, bold, or
   nothing at all.

Themes: ``default`` (colour), ``mono`` (no colour, ASCII icons -- the safe
choice for dumb terminals and ``NO_COLOR``), ``highcontrast`` (bright,
maximum legibility on tiny phone screens in daylight).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

__all__ = [
    "ICONS",
    "TOKENS",
    "Theme",
    "THEMES",
    "DEFAULT_THEME",
    "get_theme",
    "theme_names",
]

#: name -> (unicode/emoji glyph, ASCII fallback).
#:
#: Most glyphs are deliberately single-cell so narrow layouts stay honest; the
#: handful of true emoji (rocket/phone/robot/spark) are only used in places
#: that measure with ``rich.cells.cell_len``.
ICONS: Dict[str, Tuple[str, str]] = {
    "ok": ("✓", "+"),
    "warn": ("▲", "!"),
    "err": ("✗", "x"),
    "info": ("ℹ", "i"),
    "arrow": ("→", "->"),
    "bullet": ("•", "*"),
    "spark": ("✦", "*"),
    "folder": ("▸", ">"),
    "file": ("▪", "-"),
    "gear": ("⚙", "%"),
    "rocket": ("🚀", ">>"),
    "phone": ("📱", "[]"),
    "robot": ("🤖", "AI"),
    "star": ("★", "*"),
    "back": ("←", "<-"),
    "quit": ("⏻", "q"),
    "run": ("▶", ">"),
    "plan": ("☰", "="),
    "edit": ("✎", "~"),
    "search": ("⌕", "?"),
    "check": ("☑", "[x]"),
    "cross": ("☒", "[ ]"),
    "dot": ("·", "."),
}

#: Style tokens every theme must define.
TOKENS = (
    "accent",
    "muted",
    "ok",
    "warn",
    "err",
    "info",
    "heading",
    "key",
    "panel",
    "dim_rule",
)

_DEFAULT_STYLES: Dict[str, str] = {
    "accent": "bold cyan",
    "muted": "grey58",
    "ok": "bold green",
    "warn": "bold yellow",
    "err": "bold red",
    "info": "cyan",
    "heading": "bold white",
    "key": "bold bright_cyan",
    "panel": "cyan",
    "dim_rule": "grey37",
}

_MONO_STYLES: Dict[str, str] = {
    "accent": "bold",
    "muted": "dim",
    "ok": "bold",
    "warn": "bold",
    "err": "bold",
    "info": "",
    "heading": "bold",
    "key": "bold",
    "panel": "",
    "dim_rule": "dim",
}

_HIGHCONTRAST_STYLES: Dict[str, str] = {
    "accent": "bold bright_cyan",
    "muted": "white",
    "ok": "bold bright_green",
    "warn": "bold bright_yellow",
    "err": "bold bright_red",
    "info": "bold bright_cyan",
    "heading": "bold bright_white",
    "key": "bold bright_yellow",
    "panel": "bright_white",
    "dim_rule": "white",
}


@dataclass(frozen=True)
class Theme:
    """A named bundle of style tokens plus icon policy."""

    name: str
    styles: Dict[str, str] = field(default_factory=dict, compare=False, repr=False)
    color: bool = True
    ascii_icons: bool = False

    def icon(self, name: str, emoji: bool = True) -> str:
        """Return the glyph for ``name``.

        ``emoji=False`` (or a theme with ``ascii_icons``) yields the ASCII
        fallback. Unknown names return ``""`` so callers can concatenate the
        result without breaking their layout maths.
        """
        pair = ICONS.get(name)
        if pair is None:
            return ""
        rich_glyph, ascii_glyph = pair
        if self.ascii_icons or not emoji:
            return ascii_glyph
        return rich_glyph

    def style(self, token: str) -> str:
        """Return the rich style string for a token (``""`` when unknown).

        Colourless themes simply carry colourless style strings, so there is
        no special-casing here -- ``mono`` maps everything to ``bold``/``dim``.
        """
        return self.styles.get(token, "")

    def has_token(self, token: str) -> bool:
        return token in self.styles


THEMES: Dict[str, Theme] = {
    "default": Theme("default", dict(_DEFAULT_STYLES), color=True, ascii_icons=False),
    "mono": Theme("mono", dict(_MONO_STYLES), color=False, ascii_icons=True),
    "highcontrast": Theme(
        "highcontrast", dict(_HIGHCONTRAST_STYLES), color=True, ascii_icons=False
    ),
}

DEFAULT_THEME = THEMES["default"]


def theme_names() -> Tuple[str, ...]:
    return tuple(sorted(THEMES))


def get_theme(name: Optional[str] = None) -> Theme:
    """Resolve a theme.

    Order of precedence: ``NO_COLOR`` (always wins, forcing ``mono``), the
    explicit ``name`` argument, the ``ANYWHERE_THEME`` env var, then
    ``default``. Unknown names fall back to ``default`` rather than raising.
    """
    if os.environ.get("NO_COLOR") is not None:
        return THEMES["mono"]
    requested = (name or os.environ.get("ANYWHERE_THEME") or "").strip().lower()
    if not requested:
        return DEFAULT_THEME
    return THEMES.get(requested, DEFAULT_THEME)
