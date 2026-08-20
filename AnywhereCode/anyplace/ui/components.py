"""Phone-first rendering primitives for Anywhere Code.

Every component takes a ``rich`` Console first and an optional
:class:`~anyplace.ui.layout.Layout`. When no layout is supplied one is derived
from the console's own width, so tests only need
``Console(width=W, record=True)``.

**Hard guarantee**: for any width in 30..120, nothing rendered here ever
produces an output line wider than the console. Text is measured with
``rich.cells.cell_len`` (emoji are two cells) and truncated by us -- we never
let rich wrap a table or a panel into a mess.

Narrow-terminal strategy (< 60 columns):

* boxes are dropped in favour of a coloured left-edge bar (``▌``) -- a rounded
  box costs 4 of maybe 32 columns and Termux fonts routinely break the joins;
* tables become stacked ``Field: value`` records separated by dim rules;
* menu descriptions move to their own dim, indented line under the label;
* the banner shrinks from a full ASCII wordmark to a two-line badge.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple, Union

from rich import box
from rich.cells import cell_len
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from anyplace.ui.layout import LG, MD, SM, XS, Layout, content_width, supports_unicode
from anyplace.ui.theme import Theme, get_theme

__all__ = [
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
]

Body = Union[str, Sequence[str]]

# --------------------------------------------------------------------------
# text helpers (public)
# --------------------------------------------------------------------------


def _cut(text: str, width: int) -> str:
    """Hard-cut ``text`` to at most ``width`` display cells."""
    if width <= 0:
        return ""
    used = 0
    out: List[str] = []
    for ch in text:
        size = cell_len(ch)
        if used + size > width:
            break
        out.append(ch)
        used += size
    return "".join(out)


def count_noun(count: int, singular: str, plural: Optional[str] = None) -> str:
    """``1 thing`` / ``2 things`` -- never ``1 thing(s)``.

    A parenthetical plural reads as unfinished, and on a 40-column screen the
    three characters it costs are three characters of something useful.
    """
    word = singular if abs(count) == 1 else (plural or singular + "s")
    return "{0} {1}".format(count, word)


def truncate(text: str, width: int) -> str:
    """Truncate to ``width`` display cells, appending ``…`` (or ``...``).

    Newlines are collapsed to spaces: this always returns a single line whose
    ``cell_len`` is ``<= width``.
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        return ""
    if width <= 0:
        return ""
    flat = " ".join(str(text).split("\n"))
    if cell_len(flat) <= width:
        return flat
    ellipsis = "…" if supports_unicode() else "..."
    ell_w = cell_len(ellipsis)
    if width <= ell_w:
        return _cut(flat, width)
    return _cut(flat, width - ell_w).rstrip() + ellipsis


def wrap(text: str, width: int, indent: str = "") -> str:
    """Word-wrap ``text`` to ``width`` cells, prefixing every line with ``indent``.

    Words longer than the available space (URLs, paths, emoji runs) are hard
    split on cell boundaries rather than overflowing. The returned string is
    newline joined and no line ever exceeds ``width`` cells.
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 20
    width = max(1, width)
    indent = str(indent)
    if cell_len(indent) >= width:
        indent = _cut(indent, max(0, width - 1))
    avail = max(1, width - cell_len(indent))

    lines: List[str] = []
    raw = str(text)
    paragraphs = raw.split("\n") if raw else [""]
    for para in paragraphs:
        words = para.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            chunks: List[str] = []
            rest = word
            while cell_len(rest) > avail:
                head = _cut(rest, avail)
                if not head:  # a single glyph wider than avail
                    head = rest[0]
                    rest = rest[1:]
                else:
                    rest = rest[len(head):]
                chunks.append(head)
            chunks.append(rest)
            for i, chunk in enumerate(chunks):
                if not chunk and i:
                    continue
                if not current:
                    current = chunk
                elif cell_len(current) + 1 + cell_len(chunk) <= avail:
                    current = current + " " + chunk
                else:
                    lines.append(current)
                    current = chunk
        lines.append(current)
    return "\n".join(indent + line if line else "" for line in lines)


# --------------------------------------------------------------------------
# internal plumbing
# --------------------------------------------------------------------------


def _layout_for(console: Optional[Console], layout: Optional[Layout]) -> Layout:
    """Resolve the layout to render with.

    Explicit layout wins; otherwise we measure the console itself (clamped by
    ``ANYWHERE_WIDTH`` when the user pinned one) so a component can never draw
    wider than the surface it is printing to.
    """
    if layout is not None:
        return layout
    width = None
    if console is not None:
        try:
            width = int(console.width)
        except Exception:  # pragma: no cover - defensive
            width = None
    if width is None:
        return Layout.detect()
    pinned = _pinned_width()
    if pinned:
        # A user-pinned ANYWHERE_WIDTH narrows the layout, but can never make
        # us draw wider than the console we are printing to.
        width = min(width, pinned)
    return Layout.detect(width=width)


def _pinned_width() -> Optional[int]:
    raw = (os.environ.get("ANYWHERE_WIDTH") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return None


def _render_width(console: Optional[Console], layout: Layout) -> int:
    """Never draw wider than either the layout or the real console."""
    width = layout.width
    if console is not None:
        try:
            width = min(width, int(console.width))
        except Exception:  # pragma: no cover - defensive
            pass
    return max(1, width)


def _emit(console: Console, renderable: Any) -> None:
    console.print(
        renderable,
        no_wrap=True,
        overflow="crop",
        crop=True,
        markup=False,
        highlight=False,
    )


def _emit_block(console: Console, renderable: Any, layout: Layout) -> None:
    """Print a boxed renderable indented into the gutter, like the text lines.

    ``Padding`` expands the block to the console width, so the visible box can
    never be wider than the terminal.
    """
    if layout.gutter:
        renderable = Padding(renderable, (0, 0, 0, layout.gutter))
    _emit(console, renderable)


def _line(console: Console, text: Text, width: int) -> None:
    """Print a single Text line, defensively cropped to ``width``."""
    if cell_len(text.plain) > width:
        text.truncate(len(_cut(text.plain, width)))
    _emit(console, text)


def _glyphs(layout: Layout) -> Tuple[str, str, str]:
    """(bar, horizontal rule char, separator) respecting unicode support."""
    if layout.unicode:
        return "▌", "─", "·"
    return "|", "-", "|"


def _body_lines(body: Body) -> List[str]:
    if body is None:
        return []
    if isinstance(body, str):
        return body.split("\n")
    out: List[str] = []
    for item in body:
        out.extend(str(item).split("\n"))
    return out


def _tone_style(theme: Theme, tone: str) -> str:
    token = {
        "info": "info",
        "ok": "ok",
        "success": "ok",
        "warn": "warn",
        "warning": "warn",
        "err": "err",
        "error": "err",
        "danger": "err",
        "accent": "accent",
        "muted": "muted",
        "heading": "heading",
    }.get((tone or "info").lower(), "info")
    return theme.style(token)


_STATUS_ICONS = {
    "pass": ("ok", "ok"),
    "ok": ("ok", "ok"),
    "done": ("ok", "ok"),
    "fail": ("err", "err"),
    "err": ("err", "err"),
    "error": ("err", "err"),
    "warn": ("warn", "warn"),
    "warning": ("warn", "warn"),
    "skip": ("dot", "muted"),
    "skipped": ("dot", "muted"),
    "run": ("run", "accent"),
    "running": ("run", "accent"),
    "active": ("run", "accent"),
    "current": ("run", "accent"),
    "todo": ("dot", "muted"),
    "pending": ("dot", "muted"),
    "": ("dot", "muted"),
}


# --------------------------------------------------------------------------
# banner
# --------------------------------------------------------------------------

_WORDMARK = {
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #"),
    "Y": ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
    "W": ("#   #", "#   #", "# # #", "## ##", "#   #"),
    "H": ("#   #", "#   #", "#####", "#   #", "#   #"),
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "O": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "D": ("#### ", "#   #", "#   #", "#   #", "#### "),
    " ": ("  ", "  ", "  ", "  ", "  "),
}

_TITLE = "ANYWHERE CODE"


def _wordmark_rows(unicode_ok: bool) -> List[str]:
    rows = []
    for r in range(5):
        parts = [_WORDMARK[ch][r] for ch in _TITLE]
        line = " ".join(parts)
        rows.append(line.replace("#", "█") if unicode_ok else line)
    return rows


def banner(console: Console, layout: Optional[Layout] = None, subtitle: str = "") -> None:
    """The product wordmark, in three tiers.

    * ``lg``  -- full five-row ASCII/block wordmark plus a rule.
    * ``md``  -- one-line lockup: name, a rule that fills the gap, subtitle.
    * ``xs``/``sm`` -- a tight two-line badge that fits inside 30 columns.

    It never wraps at any width.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    bar, hbar, _ = _glyphs(lay)
    accent = theme.style("accent")
    muted = theme.style("muted")
    rule_style = theme.style("dim_rule")

    rows = _wordmark_rows(lay.unicode)
    mark_w = max(cell_len(r) for r in rows)

    if lay.bp == LG and mark_w + lay.gutter <= width:
        pad = " " * lay.gutter
        for row in rows:
            _line(console, Text(pad + row, style=accent), width)
        tag = subtitle or "AI coding that fits in your pocket"
        inner = width - lay.gutter
        line = Text(pad)
        line.append(truncate(tag, max(0, inner - 2)), style=muted)
        _line(console, line, width)
        _line(console, Text(pad + hbar * max(0, inner), style=rule_style), width)
        return

    if lay.bp == MD or (lay.bp == LG and mark_w + lay.gutter > width):
        pad = " " * lay.gutter
        inner = width - lay.gutter
        text = Text(pad)
        text.append(_TITLE, style=accent)
        used = cell_len(_TITLE)
        tail = truncate(subtitle, max(0, inner - used - 8)) if subtitle else ""
        fill = inner - used - cell_len(tail) - (2 if tail else 1)
        if fill < 3:
            tail = ""
            fill = inner - used - 1
        if fill > 0:
            text.append(" " + hbar * fill, style=rule_style)
        if tail:
            text.append(" " + tail, style=muted)
        _line(console, text, width)
        return

    # xs / sm: two-line badge
    inner = max(1, width - lay.gutter - 2)
    pad = " " * lay.gutter
    top = Text(pad)
    top.append(bar + " ", style=accent)
    top.append(truncate(_TITLE, inner), style=accent)
    _line(console, top, width)

    bottom = Text(pad)
    bottom.append(bar + " ", style=accent)
    if subtitle:
        bottom.append(truncate(subtitle, inner), style=muted)
    else:
        bottom.append(hbar * min(inner, cell_len(_TITLE)), style=rule_style)
    _line(console, bottom, width)


# --------------------------------------------------------------------------
# card
# --------------------------------------------------------------------------


def card(
    console: Console,
    body: Body,
    title: str = "",
    tone: str = "info",
    layout: Optional[Layout] = None,
) -> None:
    """A block of prose.

    Wide terminals get a rounded panel. Narrow terminals get a coloured
    left-edge bar plus a heading line -- a box would cost four columns and
    Termux fonts often break the corner joins.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    bar, hbar, _ = _glyphs(lay)
    tone_style = _tone_style(theme, tone)
    lines = _body_lines(body)

    if not lay.narrow:
        panel_w = min(width - (2 * lay.gutter), content_width(width, 100))
        inner = max(4, panel_w - 4)
        text = Text()
        first = True
        for raw in lines:
            for wrapped in wrap(raw, inner).split("\n"):
                if not first:
                    text.append("\n")
                text.append(wrapped)
                first = False
        panel = Panel(
            text,
            title=truncate(title, max(0, panel_w - 8)) if title else None,
            title_align="left",
            box=box.ROUNDED if lay.unicode else box.ASCII,
            border_style=tone_style,
            padding=(0, 1),
            width=panel_w,
            expand=True,
        )
        _emit_block(console, panel, lay)
        return

    pad = " " * lay.gutter
    inner = max(4, width - lay.gutter - 2)
    if title:
        head = Text(pad)
        head.append(bar + " ", style=tone_style)
        head.append(truncate(title, inner), style=theme.style("heading"))
        _line(console, head, width)
    for raw in lines:
        for wrapped in wrap(raw, inner).split("\n"):
            line = Text(pad)
            line.append(bar + " ", style=tone_style)
            line.append(wrapped)
            _line(console, line, width)


# --------------------------------------------------------------------------
# menu
# --------------------------------------------------------------------------


@dataclass
class MenuItem:
    """One selectable row. ``key`` is the thing the user taps."""

    key: str
    label: str
    description: str = ""
    icon: str = ""
    disabled: bool = False
    badge: str = ""


def menu(
    console: Console,
    items: Sequence[MenuItem],
    title: str = "",
    layout: Optional[Layout] = None,
    footer: str = "",
) -> None:
    """A numbered menu.

    Narrow: one item per line, label first, description dim-wrapped underneath
    and indented. Wide: two aligned columns of ``key. label`` and description.
    The keys are rendered prominently because they are the tap targets.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(8, width - lay.gutter)
    key_style = theme.style("key")
    muted = theme.style("muted")

    if title:
        head = Text(pad)
        head.append(truncate(title, inner), style=theme.style("heading"))
        _line(console, head, width)

    if not items:
        _line(console, Text(pad + truncate("(nothing available)", inner), style=muted), width)
        return

    key_w = max(cell_len(str(i.key)) for i in items)
    key_w = min(key_w, 4)
    marker_w = key_w + 2  # "1. "

    if lay.narrow:
        for item in items:
            style = muted if item.disabled else key_style
            line = Text(pad)
            line.append(_cut(str(item.key), key_w).rjust(key_w), style=style)
            line.append(". ", style=muted if item.disabled else "")
            label = str(item.label)
            if item.icon:
                label = "{} {}".format(item.icon, label)
            if item.badge:
                label = "{} [{}]".format(label, item.badge)
            label_style = muted if item.disabled else theme.style("heading")
            line.append(truncate(label, max(1, inner - marker_w)), style=label_style)
            _line(console, line, width)
            if item.description:
                dent = " " * marker_w
                for wrapped in wrap(item.description, inner - marker_w).split("\n"):
                    if not wrapped:
                        continue
                    sub = Text(pad + dent)
                    sub.append(wrapped, style=muted)
                    _line(console, sub, width)
        if footer:
            foot = Text(pad)
            foot.append(truncate(footer, inner), style=muted)
            _line(console, foot, width)
        return

    # wide: aligned two columns
    labels = []
    for item in items:
        label = str(item.label)
        if item.icon:
            label = "{} {}".format(item.icon, label)
        if item.badge:
            label = "{} [{}]".format(label, item.badge)
        labels.append(label)
    label_w = max(cell_len(l) for l in labels)
    left_w = min(marker_w + label_w, max(16, inner // 2))
    desc_w = inner - left_w - 2
    if desc_w < 12:
        left_w = inner
        desc_w = 0

    for item, label in zip(items, labels):
        style = muted if item.disabled else key_style
        line = Text(pad)
        line.append(_cut(str(item.key), key_w).rjust(key_w), style=style)
        line.append(". ", style="")
        label_style = muted if item.disabled else theme.style("heading")
        shown = truncate(label, max(1, left_w - marker_w))
        line.append(shown, style=label_style)
        if desc_w > 0 and item.description:
            gap = left_w - marker_w - cell_len(shown) + 2
            line.append(" " * max(1, gap))
            line.append(truncate(item.description, desc_w), style=muted)
        _line(console, line, width)

    if footer:
        foot = Text(pad)
        foot.append(truncate(footer, inner), style=muted)
        _line(console, foot, width)


# --------------------------------------------------------------------------
# key/value + tables
# --------------------------------------------------------------------------


def kv(
    console: Console,
    pairs: Sequence[Tuple[str, str]],
    layout: Optional[Layout] = None,
    title: str = "",
) -> None:
    """Aligned label/value pairs; stacks vertically when there is no room."""
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(8, width - lay.gutter)
    muted = theme.style("muted")

    if title:
        head = Text(pad)
        head.append(truncate(title, inner), style=theme.style("heading"))
        _line(console, head, width)

    if not pairs:
        return

    key_w = max(cell_len(str(k)) for k, _ in pairs)
    key_w = min(key_w, max(6, inner // 3))
    stacked = (inner - key_w - 2) < 12

    for raw_key, raw_value in pairs:
        key_text = str(raw_key)
        value_text = "" if raw_value is None else str(raw_value)
        if stacked:
            line = Text(pad)
            line.append(truncate(key_text, inner), style=theme.style("key"))
            _line(console, line, width)
            for wrapped in wrap(value_text, inner - 2, indent="  ").split("\n"):
                if not wrapped:
                    continue
                _line(console, Text(pad + wrapped), width)
        else:
            first = True
            avail = inner - key_w - 2
            for wrapped in wrap(value_text, avail).split("\n"):
                line = Text(pad)
                if first:
                    line.append(truncate(key_text, key_w).ljust(key_w), style=theme.style("key"))
                    first = False
                else:
                    line.append(" " * key_w)
                line.append("  ")
                line.append(wrapped)
                _line(console, line, width)
            if first:  # empty value
                line = Text(pad)
                line.append(truncate(key_text, key_w).ljust(key_w), style=theme.style("key"))
                line.append("  ")
                line.append(truncate("-", avail), style=muted)
                _line(console, line, width)


def _column_budgets(
    cols: Sequence[str],
    rows: Sequence[Sequence[str]],
    avail: int,
    ncols: int,
) -> List[int]:
    """Share ``avail`` columns between table columns.

    Columns start at their natural width; if that overflows we repeatedly
    shave a cell off whichever column is currently widest, so short columns
    (``Type``, ``Files``) keep their slack instead of every column being
    squeezed to the same arbitrary size.
    """
    natural = []
    for i, col in enumerate(cols):
        widest = cell_len(str(col))
        for row in rows:
            if i < len(row):
                cell = "" if row[i] is None else str(row[i])
                widest = max(widest, cell_len(cell))
        natural.append(max(3, widest))
    if sum(natural) <= avail:
        return natural

    budgets = list(natural)
    floor = max(3, avail // (ncols * 3) or 3)
    while sum(budgets) > avail:
        widest = max(budgets)
        if widest <= floor:
            break
        budgets[budgets.index(widest)] = widest - 1
    # Last resort for absurdly narrow tables: hard-share what is left.
    if sum(budgets) > avail:
        share = max(1, avail // ncols)
        budgets = [share] * ncols
    return budgets


def data_table(
    console: Console,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    layout: Optional[Layout] = None,
    title: str = "",
) -> None:
    """Tabular data.

    ``width >= 60`` renders a real rich Table with every cell pre-truncated to
    its column budget (rich is never allowed to wrap). Below 60 the table is
    transposed into stacked ``Field: value`` records separated by dim rules,
    which is the only thing that stays readable on a phone.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(8, width - lay.gutter)
    muted = theme.style("muted")
    _, hbar, _ = _glyphs(lay)
    cols = [str(c) for c in columns]

    if title:
        head = Text(pad)
        head.append(truncate(title, inner), style=theme.style("heading"))
        _line(console, head, width)

    if not cols:
        return

    if not rows:
        _line(console, Text(pad + truncate("(no rows)", inner), style=muted), width)
        return

    if not lay.narrow:
        ncols = len(cols)
        use_box = box.ROUNDED if lay.unicode else box.ASCII
        overhead = (3 * ncols) + 1  # one padded cell per column + n+1 borders
        budgets = _column_budgets(cols, rows, max(ncols * 3, inner - overhead), ncols)
        table = Table(
            box=use_box,
            width=min(inner, overhead + sum(budgets)),
            header_style=theme.style("heading"),
            border_style=theme.style("dim_rule"),
            show_edge=True,
            expand=False,
        )
        for col, budget in zip(cols, budgets):
            table.add_column(
                truncate(col, budget), no_wrap=True, overflow="ellipsis", max_width=budget
            )
        for row in rows:
            cells = [
                truncate("" if c is None else str(c), b) for c, b in zip(row, budgets)
            ]
            cells += [""] * (ncols - len(cells))
            table.add_row(*cells[:ncols])
        _emit_block(console, table, lay)
        return

    label_w = max(cell_len(c) for c in cols)
    label_w = min(label_w, max(6, inner // 3))
    for idx, row in enumerate(rows):
        if idx:
            _line(console, Text(pad + hbar * inner, style=theme.style("dim_rule")), width)
        values = list(row) + [""] * (len(cols) - len(row))
        for col, value in zip(cols, values[: len(cols)]):
            # "Type:" then pad, so the values line up but the colon hugs the
            # label instead of floating.
            prefix = (truncate(col, label_w) + ":").ljust(label_w + 2)
            avail = inner - cell_len(prefix)
            if avail < 8:
                line = Text(pad)
                line.append(truncate(col + ":", inner), style=theme.style("key"))
                _line(console, line, width)
                for wrapped in wrap("" if value is None else str(value), inner - 2, indent="  ").split("\n"):
                    if wrapped:
                        _line(console, Text(pad + wrapped), width)
                continue
            chunks = wrap("" if value is None else str(value), avail).split("\n")
            first_line = Text(pad)
            first_line.append(prefix, style=theme.style("key"))
            first_line.append(chunks[0] if chunks else "")
            _line(console, first_line, width)
            for extra in chunks[1:]:
                if extra:
                    _line(console, Text(pad + " " * cell_len(prefix) + extra), width)


# --------------------------------------------------------------------------
# steps / rules / hints / progress
# --------------------------------------------------------------------------


def steps(
    console: Console,
    items: Sequence[Tuple[str, str, str]],
    layout: Optional[Layout] = None,
) -> None:
    """A checklist of ``(status, name, detail)`` rows."""
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(8, width - lay.gutter)
    muted = theme.style("muted")

    names = [str(item[1]) if len(item) > 1 else "" for item in items]
    name_w = max([cell_len(n) for n in names] or [0])

    for item in items:
        status = str(item[0]).lower() if len(item) > 0 else ""
        name = str(item[1]) if len(item) > 1 else ""
        detail = str(item[2]) if len(item) > 2 else ""
        icon_name, token = _STATUS_ICONS.get(status, ("dot", "muted"))
        glyph = theme.icon(icon_name, emoji=lay.emoji)
        marker = glyph + " " if glyph else ""
        marker_w = cell_len(marker)
        style = theme.style(token)

        if lay.narrow or not detail:
            line = Text(pad)
            line.append(marker, style=style)
            line.append(truncate(name, max(1, inner - marker_w)))
            _line(console, line, width)
            if detail:
                dent = " " * marker_w
                for wrapped in wrap(detail, inner - marker_w).split("\n"):
                    if wrapped:
                        sub = Text(pad + dent)
                        sub.append(wrapped, style=muted)
                        _line(console, sub, width)
            continue

        col = min(name_w, max(10, inner // 3))
        line = Text(pad)
        line.append(marker, style=style)
        shown = truncate(name, col)
        line.append(shown)
        line.append(" " * max(1, col - cell_len(shown) + 2))
        avail = inner - marker_w - col - 2
        if avail >= 6:
            line.append(truncate(detail, avail), style=muted)
        _line(console, line, width)


def hint_bar(
    console: Console,
    hints: Sequence[Tuple[str, str]],
    layout: Optional[Layout] = None,
) -> None:
    """The persistent bottom bar, e.g. ``1-5 pick · b back · q quit``.

    Hints are assumed to be in priority order; when the bar will not fit, the
    least important (rightmost) hints are dropped rather than wrapping.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(4, width - lay.gutter)
    _, _, dot = _glyphs(lay)
    sep = " {} ".format(dot)
    key_style = theme.style("key")
    muted = theme.style("muted")

    pairs = [(str(k), str(v)) for k, v in hints if str(k) or str(v)]
    if not pairs:
        return

    def measure(selected: Sequence[Tuple[str, str]]) -> int:
        total = 0
        for i, (k, v) in enumerate(selected):
            if i:
                total += cell_len(sep)
            total += cell_len(k) + (1 + cell_len(v) if v else 0)
        return total

    chosen = list(pairs)
    while len(chosen) > 1 and measure(chosen) > inner:
        chosen.pop()

    line = Text(pad)
    if measure(chosen) > inner:
        k, v = chosen[0]
        line.append(truncate("{} {}".format(k, v).strip(), inner), style=key_style)
        _line(console, line, width)
        return

    for i, (k, v) in enumerate(chosen):
        if i:
            line.append(sep, style=muted)
        line.append(k, style=key_style)
        if v:
            line.append(" " + v, style=muted)
    _line(console, line, width)


def rule(console: Console, label: str = "", layout: Optional[Layout] = None) -> None:
    """A horizontal rule, optionally labelled: ``── label ────────``."""
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(2, width - lay.gutter)
    _, hbar, _ = _glyphs(lay)
    rule_style = theme.style("dim_rule")

    if not label:
        _line(console, Text(pad + hbar * inner, style=rule_style), width)
        return

    lead = 2 if inner > 8 else 1
    shown = truncate(label, max(1, inner - lead - 3))
    tail = inner - lead - cell_len(shown) - 2
    line = Text(pad)
    line.append(hbar * lead, style=rule_style)
    line.append(" " + shown + " ", style=theme.style("heading"))
    if tail > 0:
        line.append(hbar * tail, style=rule_style)
    _line(console, line, width)


def progress_line(
    console: Console,
    index: int,
    total: int,
    label: str,
    layout: Optional[Layout] = None,
) -> None:
    """A one-line progress indicator that shrinks with the terminal.

    At ``xs`` the bar disappears entirely and you get ``[3/12] file.tsx``.
    """
    lay = _layout_for(console, layout)
    theme = get_theme()
    width = _render_width(console, lay)
    pad = " " * lay.gutter
    inner = max(6, width - lay.gutter)
    accent = theme.style("accent")
    muted = theme.style("muted")

    try:
        total_i = max(0, int(total))
        index_i = max(0, int(index))
    except (TypeError, ValueError):
        total_i, index_i = 0, 0
    if total_i:
        index_i = min(index_i, total_i)
        frac = index_i / float(total_i)
    else:
        frac = 0.0

    counter = "[{}/{}] ".format(index_i, total_i)
    line = Text(pad)
    line.append(counter, style=accent)
    remaining = inner - cell_len(counter)

    if lay.bp != XS and remaining >= 16:
        bar_w = max(6, min(24, inner // 4))
        bar_w = min(bar_w, max(0, remaining - 10))
        if bar_w >= 4:
            filled = int(round(frac * bar_w))
            filled = max(0, min(bar_w, filled))
            fill_ch, empty_ch = ("█", "░") if lay.unicode else ("#", ".")
            line.append(fill_ch * filled, style=theme.style("ok"))
            line.append(empty_ch * (bar_w - filled), style=theme.style("dim_rule"))
            pct = " {:>3d}% ".format(int(round(frac * 100)))
            line.append(pct, style=muted)
            remaining -= bar_w + cell_len(pct)

    if remaining > 1 and label:
        line.append(truncate(str(label), remaining))
    _line(console, line, width)
