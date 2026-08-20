"""Terminal capability + breakpoint detection for Anywhere Code.

Pure stdlib: this module never imports ``rich`` or ``click`` so it can be used
from any layer (including pure-logic modules) and tested headlessly.

Breakpoints (canonical for the whole app)::

    xs   width < 40    phone portrait, small font
    sm   40 <= w < 60  phone portrait, normal font
    md   60 <= w < 90  phone landscape / small tablet
    lg   width >= 90   desktop

``narrow`` means ``width < 60`` (xs or sm) -- phone-first rules apply.

Environment overrides (all optional):

``ANYWHERE_WIDTH`` / ``ANYWHERE_HEIGHT``
    Force the reported terminal size. Invaluable for testing and for users
    whose Termux setup reports nonsense.
``NO_COLOR``
    Presence (any value, including empty) disables colour, per no-color.org.
``FORCE_COLOR``
    Force colour back on.
``ANYWHERE_THEME``
    ``default`` | ``mono`` | ``highcontrast``. ``mono`` also implies no colour
    and no emoji.
``ANYWHERE_UNICODE`` / ``ANYWHERE_ASCII``
    Force unicode box/bar glyphs on or off.
``ANYWHERE_EMOJI``
    Force emoji icons on or off.
``ANYWHERE_TERMUX``
    Force Termux detection on or off.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = [
    "XS",
    "SM",
    "MD",
    "LG",
    "BREAKPOINTS",
    "MIN_WIDTH",
    "NARROW_BELOW",
    "terminal_size",
    "breakpoint_for",
    "is_narrow",
    "is_termux",
    "supports_unicode",
    "supports_emoji",
    "supports_color",
    "content_width",
    "Layout",
]

XS, SM, MD, LG = "xs", "sm", "md", "lg"

#: Ordered (name, minimum width) pairs.
BREAKPOINTS = ((XS, 0), (SM, 40), (MD, 60), (LG, 90))

#: Anything narrower than this is "phone-first".
NARROW_BELOW = 60

#: We refuse to lay out below this; nothing readable fits.
MIN_WIDTH = 20
MIN_HEIGHT = 4

_TRUEISH = frozenset({"1", "true", "yes", "y", "on"})
_FALSEISH = frozenset({"0", "false", "no", "n", "off"})


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _flag(name: str, default: Optional[bool] = None) -> Optional[bool]:
    """Read a tri-state boolean env var. Returns ``default`` when unset/junk."""
    raw = _env(name).lower()
    if raw in _TRUEISH:
        return True
    if raw in _FALSEISH:
        return False
    return default


def _positive_int(raw: str) -> Optional[int]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def terminal_size(default_width: int = 80, default_height: int = 24) -> Tuple[int, int]:
    """Best-effort terminal size as ``(width, height)``.

    ``ANYWHERE_WIDTH`` / ``ANYWHERE_HEIGHT`` win over everything else so a user
    on a broken Termux font (or a test) can pin the layout.
    """
    width = _positive_int(_env("ANYWHERE_WIDTH"))
    height = _positive_int(_env("ANYWHERE_HEIGHT"))

    if width is None or height is None:
        try:
            size = shutil.get_terminal_size(fallback=(default_width, default_height))
            detected_w, detected_h = int(size.columns), int(size.lines)
        except Exception:  # pragma: no cover - defensive
            detected_w, detected_h = default_width, default_height
        if detected_w <= 0:
            detected_w = default_width
        if detected_h <= 0:
            detected_h = default_height
        if width is None:
            width = detected_w
        if height is None:
            height = detected_h

    return max(MIN_WIDTH, width), max(MIN_HEIGHT, height)


def breakpoint_for(width: int) -> str:
    """Map a column count onto one of ``xs`` / ``sm`` / ``md`` / ``lg``."""
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 80
    name = XS
    for candidate, minimum in BREAKPOINTS:
        if width >= minimum:
            name = candidate
    return name


def is_narrow(width: Optional[int] = None) -> bool:
    """True when phone-first rules apply (``width < 60``)."""
    if width is None:
        width = terminal_size()[0]
    return int(width) < NARROW_BELOW


def is_termux() -> bool:
    """Detect Android/Termux, where fonts and box drawing are unreliable."""
    forced = _flag("ANYWHERE_TERMUX")
    if forced is not None:
        return forced
    if _env("TERMUX_VERSION"):
        return True
    if "com.termux" in _env("PREFIX"):
        return True
    if "com.termux" in _env("HOME"):
        return True
    return False


def supports_unicode() -> bool:
    """Whether box-drawing / block glyphs are safe to emit."""
    forced = _flag("ANYWHERE_UNICODE")
    if forced is not None:
        return forced
    ascii_forced = _flag("ANYWHERE_ASCII")
    if ascii_forced is not None:
        return not ascii_forced
    if _env("NO_UNICODE"):
        return False
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if not encoding:
        return True
    return "utf" in encoding


def supports_emoji() -> bool:
    """Whether double-width emoji icons are safe to emit.

    Emoji are strictly opt-out: many Termux fonts render them as tofu and the
    double-width cells corrupt layout maths, so callers should always be able
    to fall back to the ASCII variants.
    """
    forced = _flag("ANYWHERE_EMOJI")
    if forced is not None:
        return forced and supports_unicode()
    if not supports_unicode():
        return False
    if _env("ANYWHERE_THEME").lower() == "mono":
        return False
    return True


def supports_color() -> bool:
    """Whether to emit colour at all (``NO_COLOR`` / ``mono`` theme aware)."""
    if _flag("FORCE_COLOR", False):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    if _env("ANYWHERE_THEME").lower() == "mono":
        return False
    return True


def content_width(width: Optional[int] = None, max_width: int = 100) -> int:
    """Usable content width: the terminal width capped at ``max_width``."""
    if width is None:
        width = terminal_size()[0]
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 80
    return max(MIN_WIDTH, min(width, int(max_width)))


@dataclass(frozen=True)
class Layout:
    """An immutable snapshot of everything a component needs to lay itself out."""

    width: int
    height: int
    bp: str
    narrow: bool
    unicode: bool
    emoji: bool
    color: bool
    termux: bool

    @classmethod
    def detect(
        cls,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> "Layout":
        """Build a Layout from the environment, with optional explicit size.

        An explicitly supplied ``width``/``height`` always wins so callers and
        tests stay deterministic; when omitted we fall back to
        :func:`terminal_size` (which honours ``ANYWHERE_WIDTH``).
        """
        det_w, det_h = terminal_size()
        eff_w = det_w if width is None else max(MIN_WIDTH, int(width))
        eff_h = det_h if height is None else max(MIN_HEIGHT, int(height))
        return cls(
            width=eff_w,
            height=eff_h,
            bp=breakpoint_for(eff_w),
            narrow=is_narrow(eff_w),
            unicode=supports_unicode(),
            emoji=supports_emoji(),
            color=supports_color(),
            termux=is_termux(),
        )

    # -- derived geometry -------------------------------------------------
    @property
    def gutter(self) -> int:
        """Left padding in columns: 0 on xs, 1 on sm, 2 otherwise."""
        if self.bp == XS:
            return 0
        if self.bp == SM:
            return 1
        return 2

    @property
    def body_width(self) -> int:
        """Columns available for content once gutters are removed."""
        return max(MIN_WIDTH, self.width - (self.gutter * 2))

    @property
    def pad(self) -> str:
        """Left gutter as a literal string."""
        return " " * self.gutter

    def with_width(self, width: int) -> "Layout":
        """A copy of this layout re-measured at a different width."""
        return Layout.detect(width=width, height=self.height)
