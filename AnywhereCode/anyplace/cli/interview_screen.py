"""
The guided interview, on screen.

Pure presentation: `anyplace.core.interview` decides *what* to ask and in what
order; this module decides how it looks and how a thumb answers it. One question
per screen, numbered options, Enter for the default, `b` to go back.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from anyplace.core.brief import ProjectBrief
from anyplace.core.interview import Interview, Question
from anyplace.ui import components as ui
from anyplace.ui.layout import Layout
from anyplace.ui.prompts import (
    Choice,
    GoBack,
    ask_choice,
    ask_multi,
    ask_text,
    ask_yes_no,
)


def _choices(question: Question) -> List[Choice]:
    """Turn a question's (value, label) options into prompt Choices."""
    return [Choice(value=value, label=label) for value, label in question.options]


def _ask_one(
    console,
    question: Question,
    layout: Layout,
    input_fn: Optional[Callable[[str], str]],
) -> Any:
    """Ask a single question using the widget its kind calls for."""
    if question.kind == "choice":
        return ask_choice(
            console,
            question.text,
            _choices(question),
            default=question.default,
            layout=layout,
            input_fn=input_fn,
            help_text=question.help,
        )

    if question.kind == "yesno":
        return ask_yes_no(
            console,
            question.text,
            default=bool(question.default),
            layout=layout,
            input_fn=input_fn,
            help_text=question.help,
        )

    if question.kind == "multi":
        return ask_multi(
            console,
            question.text,
            _choices(question),
            defaults=question.default or [],
            layout=layout,
            input_fn=input_fn,
            help_text=question.help,
        )

    return ask_text(
        console,
        question.text,
        default=question.default,
        layout=layout,
        input_fn=input_fn,
        allow_empty=not question.required,
        help_text=question.help,
        placeholder=question.placeholder,
    )


def run_interview(
    console,
    interview: Interview,
    layout: Optional[Layout] = None,
    input_fn: Optional[Callable[[str], str]] = None,
    show_header: bool = True,
) -> ProjectBrief:
    """
    Walk the user through the interview and hand back a finished brief.

    Raises QuitApp if the user bails out; GoBack on the very first question
    propagates so the caller can return to the previous screen.
    """
    layout = layout or Layout.detect()

    while True:
        question = interview.next_question()
        if question is None:
            break

        answered, total = interview.progress()
        if show_header:
            console.print()
            ui.rule(console, "Question {0} of {1}".format(answered + 1, total), layout=layout)

        try:
            value = _ask_one(console, question, layout, input_fn)
        except GoBack:
            previous = interview.back()
            if previous is None:
                raise
            continue

        interview.answer(question.id, value)

    return interview.to_brief()


def show_brief(console, brief: ProjectBrief, layout: Optional[Layout] = None) -> None:
    """Show the finished brief so the user can sanity-check it before we spend tokens."""
    layout = layout or Layout.detect()
    console.print()
    ui.kv(console, brief.summary_pairs(), layout=layout, title="Here's what I understood")
