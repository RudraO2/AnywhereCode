"""Phone-first prompts.

Typing on a phone is expensive, so every question here is answerable with a
single keystroke: options are numbered, the default is shown inline as ``[1]``
and bare Enter accepts it. Case-insensitive prefixes of the option labels work
too, so ``we`` picks "Web app".

Universal commands (documented on the hint bar of every prompt):

======  =======================================================
``b``   go back one step (raises :class:`GoBack`) when allowed
``q``   quit (raises :class:`QuitApp`)
``?``   show the question's help text and re-ask
======  =======================================================

Bad input never raises and never clears the screen: the prompt re-asks in
place after one short red line. ``EOFError``/``KeyboardInterrupt`` from the
reader become :class:`QuitApp` so a Ctrl-C on a phone keyboard cannot produce
a traceback.

Every function takes ``input_fn`` so tests can drive it headlessly; see
:func:`scripted_input`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from rich.console import Console
from rich.text import Text

from anyplace.ui.components import MenuItem, hint_bar, menu, truncate, wrap
from anyplace.ui.layout import Layout
from anyplace.ui.theme import get_theme

__all__ = [
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


class PromptAbort(Exception):
    """Base class for 'the user did not answer the question'."""


class GoBack(PromptAbort):
    """User asked to step back to the previous question."""


class QuitApp(PromptAbort):
    """User asked to leave (or the input stream closed)."""


@dataclass
class Choice:
    """One option in a choice/multi prompt. ``value`` is what gets returned."""

    value: str
    label: str
    description: str = ""
    hint: str = ""
    icon: str = ""


InputFn = Callable[[str], str]

BACK_WORDS = frozenset({"b", "back", ":b"})
QUIT_WORDS = frozenset({"q", "quit", "exit", ":q"})
HELP_WORDS = frozenset({"?", "h", "help", ":h"})
_YES_WORDS = frozenset({"y", "yes", "yeah", "yep", "ok", "true", "1"})
_NO_WORDS = frozenset({"n", "no", "nope", "false", "0", "2"})


def scripted_input(lines: Sequence[str]) -> InputFn:
    """Return an :data:`InputFn` that replays ``lines`` in order.

    Raises ``RuntimeError("input exhausted")`` once the script runs out, which
    keeps a buggy re-ask loop from spinning forever in tests.
    """
    queue = list(lines)

    def _reader(prompt: str = "") -> str:
        if not queue:
            raise RuntimeError("input exhausted")
        return queue.pop(0)

    return _reader


def _default_input(prompt: str = "") -> str:
    """The real reader: click, so terminals and pipes behave consistently."""
    import click

    try:
        return click.prompt(
            prompt, default="", show_default=False, prompt_suffix="", err=False
        )
    except click.exceptions.Abort:
        raise QuitApp("aborted")


# --------------------------------------------------------------------------
# shared plumbing
# --------------------------------------------------------------------------


def _lay(console: Optional[Console], layout: Optional[Layout]) -> Layout:
    if layout is not None:
        return layout
    width = None
    if console is not None:
        try:
            width = int(console.width)
        except Exception:  # pragma: no cover - defensive
            width = None
    return Layout.detect(width=width)


def _read(input_fn: Optional[InputFn], prompt: str) -> str:
    reader = input_fn or _default_input
    try:
        raw = reader(prompt)
    except (EOFError, KeyboardInterrupt):
        raise QuitApp("input closed")
    if raw is None:
        return ""
    return str(raw)


def _say(console: Console, text: str, style: str, layout: Layout) -> None:
    if console is None:
        return
    pad = " " * layout.gutter
    inner = max(8, layout.width - layout.gutter)
    for line in wrap(text, inner).split("\n"):
        console.print(
            Text(pad + line, style=style),
            no_wrap=True,
            overflow="crop",
            markup=False,
            highlight=False,
        )


def _error(console: Console, message: str, layout: Layout) -> None:
    theme = get_theme()
    icon = theme.icon("err", emoji=layout.emoji)
    _say(console, "{} {}".format(icon, message).strip(), theme.style("err"), layout)


def _question(console: Console, question: str, layout: Layout) -> None:
    theme = get_theme()
    icon = theme.icon("arrow", emoji=layout.emoji)
    _say(console, "{} {}".format(icon, question).strip(), theme.style("heading"), layout)


def _help(console: Console, help_text: str, layout: Layout) -> None:
    theme = get_theme()
    text = help_text or "No extra help for this question."
    icon = theme.icon("info", emoji=layout.emoji)
    _say(console, "{} {}".format(icon, text).strip(), theme.style("info"), layout)


def _command(raw: str, allow_back: bool) -> Optional[str]:
    """Classify a raw answer as a universal command, if it is one."""
    token = raw.strip().lower()
    if not token:
        return None
    if token in QUIT_WORDS:
        return "quit"
    if token in BACK_WORDS and allow_back:
        return "back"
    if token in HELP_WORDS:
        return "help"
    return None


def _handle_command(
    console: Console,
    raw: str,
    allow_back: bool,
    help_text: str,
    layout: Layout,
) -> Optional[str]:
    """Returns "help" when the caller should re-render, else None."""
    cmd = _command(raw, allow_back)
    if cmd == "quit":
        raise QuitApp("user quit")
    if cmd == "back":
        raise GoBack("user went back")
    if cmd == "help":
        _help(console, help_text, layout)
        return "help"
    return None


def _prompt_suffix(default_label: str, layout: Layout) -> str:
    theme = get_theme()
    arrow = theme.icon("arrow", emoji=layout.emoji) or ">"
    if default_label:
        return "{} [{}] ".format(arrow, default_label)
    return "{} ".format(arrow)


def _hints(
    console: Console,
    layout: Layout,
    pick: str = "",
    allow_back: bool = True,
    help_text: str = "",
) -> None:
    # Priority order matters: hint_bar drops from the right when space runs out.
    hints: List[Tuple[str, str]] = []
    if pick:
        hints.append((pick, "pick"))
    if allow_back:
        hints.append(("b", "back"))
    hints.append(("q", "quit"))
    if help_text:
        hints.append(("?", "help"))
    hint_bar(console, hints, layout=layout)


def _choice_items(choices: Sequence[Choice], default_index: Optional[int], layout: Layout) -> List[MenuItem]:
    items: List[MenuItem] = []
    for i, choice in enumerate(choices):
        badge = "default" if default_index is not None and i == default_index else ""
        if choice.hint and not badge:
            badge = choice.hint
        items.append(
            MenuItem(
                key=str(i + 1),
                label=choice.label,
                description=choice.description,
                icon=choice.icon,
                badge=badge,
            )
        )
    return items


def _resolve_default(choices: Sequence[Choice], default) -> Optional[int]:
    """Accept a value string, a label, or a 0-based index."""
    if default is None:
        return None
    if isinstance(default, bool):
        return None
    if isinstance(default, int):
        if 0 <= default < len(choices):
            return default
        return None
    token = str(default).strip().lower()
    if not token:
        return None
    for i, choice in enumerate(choices):
        if str(choice.value).lower() == token:
            return i
    for i, choice in enumerate(choices):
        if str(choice.label).lower() == token:
            return i
    if token.isdigit():
        idx = int(token) - 1
        if 0 <= idx < len(choices):
            return idx
    return None


def _match_choice(token: str, choices: Sequence[Choice]) -> Tuple[Optional[int], str]:
    """Map raw user text onto a choice index.

    Returns ``(index, error)``; exactly one is meaningful. Numbers win, then
    exact value/label matches, then unambiguous case-insensitive prefixes.
    """
    cleaned = " ".join(token.split()).strip()
    if not cleaned:
        return None, "empty"
    compact = cleaned.replace(" ", "")
    if compact.isdigit():
        idx = int(compact) - 1
        if 0 <= idx < len(choices):
            return idx, ""
        return None, "Pick a number between 1 and {}.".format(len(choices))

    low = cleaned.lower()
    for i, choice in enumerate(choices):
        if low == str(choice.value).lower() or low == str(choice.label).lower():
            return i, ""

    hits = [
        i
        for i, choice in enumerate(choices)
        if str(choice.label).lower().startswith(low) or str(choice.value).lower().startswith(low)
    ]
    if len(hits) == 1:
        return hits[0], ""
    if len(hits) > 1:
        names = ", ".join(choices[i].label for i in hits[:3])
        return None, "That matches several options ({}). Use its number.".format(names)
    return None, "I did not understand that. Enter a number 1-{}.".format(len(choices))


# --------------------------------------------------------------------------
# prompts
# --------------------------------------------------------------------------


def ask_choice(
    console: Console,
    question: str,
    choices: Sequence[Choice],
    default=None,
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
    allow_back: bool = True,
    help_text: str = "",
) -> str:
    """Ask the user to pick one option; returns the chosen ``Choice.value``."""
    lay = _lay(console, layout)
    choices = list(choices)
    if not choices:
        raise ValueError("ask_choice requires at least one choice")
    default_index = _resolve_default(choices, default)

    def render() -> None:
        _question(console, question, lay)
        menu(console, _choice_items(choices, default_index, lay), layout=lay)
        _hints(
            console,
            lay,
            pick="1-{}".format(len(choices)) if len(choices) > 1 else "1",
            allow_back=allow_back,
            help_text=help_text,
        )

    render()
    default_label = str(default_index + 1) if default_index is not None else ""
    while True:
        raw = _read(input_fn, _prompt_suffix(default_label, lay))
        if _handle_command(console, raw, allow_back, help_text, lay) == "help":
            render()
            continue
        if not raw.strip():
            if default_index is not None:
                return str(choices[default_index].value)
            _error(console, "Pick a number 1-{}.".format(len(choices)), lay)
            continue
        index, error = _match_choice(raw, choices)
        if index is None:
            _error(console, error, lay)
            continue
        return str(choices[index].value)


def ask_text(
    console: Console,
    question: str,
    default: Optional[str] = None,
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
    allow_empty: bool = False,
    validator: Optional[Callable[[str], Optional[str]]] = None,
    help_text: str = "",
    placeholder: str = "",
) -> str:
    """Free text with an inline default.

    ``validator`` returns ``None`` when the value is acceptable, or a short
    error message to show before re-asking.
    """
    lay = _lay(console, layout)
    theme = get_theme()

    def render() -> None:
        _question(console, question, lay)
        if placeholder:
            _say(console, "e.g. {}".format(placeholder), theme.style("muted"), lay)
        _hints(console, lay, allow_back=True, help_text=help_text)

    render()
    default_label = truncate(default, 18) if default else ""
    while True:
        raw = _read(input_fn, _prompt_suffix(default_label, lay))
        if _handle_command(console, raw, True, help_text, lay) == "help":
            render()
            continue
        value = raw.strip()
        if not value:
            if default is not None:
                value = str(default)
            elif not allow_empty:
                _error(console, "Please type something.", lay)
                continue
        if validator is not None:
            problem = validator(value)
            if problem:
                _error(console, str(problem), lay)
                continue
        return value


def ask_yes_no(
    console: Console,
    question: str,
    default: bool = True,
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
    help_text: str = "",
) -> bool:
    """A numbered yes/no. Accepts ``1``/``2``, ``y``/``n``, or Enter."""
    lay = _lay(console, layout)
    choices = [Choice("yes", "Yes"), Choice("no", "No")]
    default_index = 0 if default else 1

    def render() -> None:
        _question(console, question, lay)
        menu(console, _choice_items(choices, default_index, lay), layout=lay)
        _hints(console, lay, pick="1-2", allow_back=True, help_text=help_text)

    render()
    default_label = "1" if default else "2"
    while True:
        raw = _read(input_fn, _prompt_suffix(default_label, lay))
        if _handle_command(console, raw, True, help_text, lay) == "help":
            render()
            continue
        token = raw.strip().lower()
        if not token:
            return bool(default)
        if token in _YES_WORDS:
            return True
        if token in _NO_WORDS:
            return False
        _error(console, "Answer 1 for yes or 2 for no.", lay)


def ask_multi(
    console: Console,
    question: str,
    choices: Sequence[Choice],
    defaults: Optional[Sequence[str]] = None,
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
    help_text: str = "",
) -> List[str]:
    """Pick any number of options.

    Accepts ``1,3 5``, ``1 3 5``, ``all``, ``none``, label prefixes, or Enter
    for the defaults. Returns values in the order the choices were declared.
    """
    lay = _lay(console, layout)
    theme = get_theme()
    choices = list(choices)
    if not choices:
        return []

    default_values = []
    for item in defaults or []:
        idx = _resolve_default(choices, item)
        if idx is not None:
            default_values.append(str(choices[idx].value))

    items: List[MenuItem] = []
    for i, choice in enumerate(choices):
        selected = str(choice.value) in default_values
        mark = theme.icon("check" if selected else "cross", emoji=lay.emoji)
        items.append(
            MenuItem(
                key=str(i + 1),
                label="{} {}".format(mark, choice.label).strip(),
                description=choice.description,
                badge=choice.hint,
            )
        )

    def render() -> None:
        _question(console, question, lay)
        menu(console, items, layout=lay)
        sep = " · " if lay.unicode else " | "
        combos = sep.join(["1,3", "all", "none"])
        _say(
            console,
            combos if lay.narrow else "Pick several: " + combos,
            theme.style("muted"),
            lay,
        )
        _hints(console, lay, pick="1-{}".format(len(choices)), allow_back=True, help_text=help_text)

    render()
    default_label = ",".join(
        str(i + 1) for i, c in enumerate(choices) if str(c.value) in default_values
    )
    while True:
        raw = _read(input_fn, _prompt_suffix(default_label or "none", lay))
        if _handle_command(console, raw, True, help_text, lay) == "help":
            render()
            continue
        token = raw.strip().lower()
        if not token:
            return list(default_values)
        if token in ("all", "*", "a"):
            return [str(c.value) for c in choices]
        if token in ("none", "-", "0"):
            return []

        parts = [p for p in token.replace(",", " ").replace(";", " ").split() if p]
        picked: List[int] = []
        error = ""
        for part in parts:
            index, err = _match_choice(part, choices)
            if index is None:
                error = err
                break
            if index not in picked:
                picked.append(index)
        if error:
            _error(console, error, lay)
            continue
        if not picked:
            _error(console, "Pick one or more numbers, or type none.", lay)
            continue
        picked.sort()
        return [str(choices[i].value) for i in picked]


def confirm_danger(
    console: Console,
    question: str,
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
) -> bool:
    """A destructive-action confirm: only the literal word ``yes`` accepts.

    Enter, ``n`` and ``no`` decline; anything else re-asks. Deliberately more
    friction than :func:`ask_yes_no` -- this is the prompt that deletes files.
    """
    lay = _lay(console, layout)
    theme = get_theme()
    warn = theme.icon("warn", emoji=lay.emoji)
    _say(console, "{} {}".format(warn, question).strip(), theme.style("warn"), lay)
    _say(console, "Type 'yes' to confirm, Enter to cancel.", theme.style("muted"), lay)

    while True:
        raw = _read(input_fn, _prompt_suffix("no", lay))
        token = raw.strip().lower()
        if token in QUIT_WORDS:
            raise QuitApp("user quit")
        if not token or token in ("n", "no"):
            return False
        if token == "yes":
            return True
        _error(console, "Type 'yes' to confirm or press Enter to cancel.", lay)


def pause(
    console: Console,
    message: str = "",
    layout: Optional[Layout] = None,
    input_fn: Optional[InputFn] = None,
) -> None:
    """Wait for Enter. ``q`` still quits, so the user is never trapped."""
    lay = _lay(console, layout)
    theme = get_theme()
    text = message or "Press Enter to continue"
    _say(console, text, theme.style("muted"), lay)
    raw = _read(input_fn, _prompt_suffix("", lay))
    if raw.strip().lower() in QUIT_WORDS:
        raise QuitApp("user quit")
