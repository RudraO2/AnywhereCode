"""Tests for anyplace.ui.prompts.

Every prompt is driven with :func:`scripted_input`, so these run headlessly and
a re-ask loop that never terminates fails fast with "input exhausted" instead
of hanging.
"""

import pytest
from rich.cells import cell_len
from rich.console import Console

from anyplace.ui.layout import Layout
from anyplace.ui.prompts import (
    Choice,
    GoBack,
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

WIDTHS = [30, 38, 45, 55, 62, 80, 120]

ENV_VARS = (
    "ANYWHERE_WIDTH",
    "ANYWHERE_THEME",
    "ANYWHERE_UNICODE",
    "ANYWHERE_ASCII",
    "ANYWHERE_EMOJI",
    "NO_COLOR",
    "FORCE_COLOR",
)

KINDS = [
    Choice("web", "Web app", "Runs in a browser"),
    Choice("mobile", "Mobile app", "iOS and Android"),
    Choice("backend", "Backend API", "Endpoints and a database"),
]

FEATURES = [
    Choice("auth", "Accounts and login"),
    Choice("db", "Database"),
    Choice("pay", "Payments"),
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def make_console(width=60):
    return Console(
        width=width,
        record=True,
        force_terminal=False,
        color_system=None,
        legacy_windows=False,
    )


def assert_fits(console, width):
    for line in console.export_text().splitlines():
        assert cell_len(line) <= width, "{!r} exceeds {}".format(line, width)


def boom_eof(_prompt=""):
    raise EOFError


def boom_interrupt(_prompt=""):
    raise KeyboardInterrupt


# -- scripted_input --------------------------------------------------------


def test_scripted_input_replays_lines_in_order():
    reader = scripted_input(["a", "b"])
    assert reader("?") == "a"
    assert reader("?") == "b"


def test_scripted_input_raises_when_exhausted():
    reader = scripted_input([])
    with pytest.raises(RuntimeError) as excinfo:
        reader("?")
    assert "input exhausted" in str(excinfo.value)


# -- ask_choice ------------------------------------------------------------


def test_ask_choice_enter_accepts_the_default():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, default="mobile", input_fn=scripted_input([""])) == "mobile"


def test_ask_choice_marks_the_default_inline():
    console = make_console()
    ask_choice(console, "Kind?", KINDS, default="web", input_fn=scripted_input([""]))
    assert "default" in console.export_text()


def test_ask_choice_accepts_a_number():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["2"])) == "mobile"


def test_ask_choice_accepts_a_number_with_whitespace():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["  3  "])) == "backend"


def test_ask_choice_accepts_a_case_insensitive_prefix():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["WE"])) == "web"


def test_ask_choice_accepts_the_value_itself():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["backend"])) == "backend"


def test_ask_choice_rejects_ambiguous_prefix_then_accepts_number():
    choices = [Choice("a", "Postgres"), Choice("b", "Postgres pooled")]
    console = make_console()
    result = ask_choice(console, "DB?", choices, input_fn=scripted_input(["post", "1"]))
    assert result == "a"
    assert "several" in console.export_text().lower()


def test_ask_choice_exact_label_beats_ambiguous_prefix():
    choices = [Choice("a", "Postgres"), Choice("b", "Postgres pooled")]
    console = make_console()
    assert ask_choice(console, "DB?", choices, input_fn=scripted_input(["Postgres"])) == "a"


def test_ask_choice_out_of_range_then_valid():
    console = make_console()
    result = ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["9", "1"]))
    assert result == "web"
    assert "between 1 and 3" in console.export_text()


def test_ask_choice_garbage_then_valid():
    console = make_console()
    result = ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["zzz!!", "2"]))
    assert result == "mobile"
    assert "did not understand" in console.export_text().lower()


def test_ask_choice_shows_only_one_error_line_per_mistake():
    console = make_console()
    ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["zzz", "1"]))
    text = console.export_text()
    assert text.lower().count("did not understand") == 1


def test_ask_choice_enter_without_default_reasks():
    console = make_console()
    result = ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["", "3"]))
    assert result == "backend"
    assert "Pick a number" in console.export_text()


def test_ask_choice_back_raises_go_back():
    console = make_console()
    with pytest.raises(GoBack):
        ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["b"]))


def test_ask_choice_back_word_raises_go_back():
    console = make_console()
    with pytest.raises(GoBack):
        ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["back"]))


def test_ask_choice_back_is_not_a_command_when_not_allowed():
    """With allow_back off, "b" is just text -- here it prefixes "Backend API"."""
    console = make_console()
    result = ask_choice(
        console, "Kind?", KINDS, input_fn=scripted_input(["b"]), allow_back=False
    )
    assert result == "backend"


def test_ask_choice_hides_the_back_hint_when_not_allowed():
    console = make_console()
    ask_choice(console, "Kind?", KINDS, default="web", input_fn=scripted_input([""]), allow_back=False)
    assert "back" not in console.export_text()


def test_ask_choice_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["q"]))


def test_quit_and_go_back_share_a_base_class():
    assert issubclass(GoBack, PromptAbort) and issubclass(QuitApp, PromptAbort)


def test_ask_choice_help_then_answer():
    console = make_console()
    result = ask_choice(
        console,
        "Kind?",
        KINDS,
        input_fn=scripted_input(["?", "1"]),
        help_text="Pick the closest match; you can change it later.",
    )
    assert result == "web"
    assert "closest match" in console.export_text()


def test_ask_choice_help_word_works_too():
    console = make_console()
    result = ask_choice(
        console, "Kind?", KINDS, input_fn=scripted_input(["h", "1"]), help_text="Some guidance"
    )
    assert result == "web"
    assert "Some guidance" in console.export_text()


def test_ask_choice_help_without_help_text_still_reasks():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["?", "1"])) == "web"


def test_ask_choice_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_choice(console, "Kind?", KINDS, input_fn=boom_eof)


def test_ask_choice_keyboard_interrupt_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_choice(console, "Kind?", KINDS, input_fn=boom_interrupt)


def test_ask_choice_exhausted_script_raises_runtime_error():
    console = make_console()
    with pytest.raises(RuntimeError):
        ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["nope"]))


def test_ask_choice_requires_at_least_one_choice():
    console = make_console()
    with pytest.raises(ValueError):
        ask_choice(console, "Kind?", [], input_fn=scripted_input([""]))


def test_ask_choice_accepts_an_integer_default():
    console = make_console()
    assert ask_choice(console, "Kind?", KINDS, default=2, input_fn=scripted_input([""])) == "backend"


def test_ask_choice_ignores_an_unknown_default():
    console = make_console()
    result = ask_choice(console, "Kind?", KINDS, default="nope", input_fn=scripted_input(["", "1"]))
    assert result == "web"


@pytest.mark.parametrize("width", WIDTHS)
def test_ask_choice_render_fits_every_width(width):
    console = make_console(width)
    ask_choice(
        console,
        "What are you building today, in broad strokes?",
        KINDS,
        default="web",
        input_fn=scripted_input(["zz", ""]),
        help_text="Pick the closest match.",
    )
    assert_fits(console, width)


@pytest.mark.parametrize("width", WIDTHS)
def test_ask_choice_shows_numbers_and_labels_at_every_width(width):
    console = make_console(width)
    ask_choice(console, "Kind?", KINDS, default="web", input_fn=scripted_input([""]))
    text = console.export_text()
    for i, choice in enumerate(KINDS, start=1):
        assert str(i) in text
        assert choice.label in text


# -- ask_text --------------------------------------------------------------


def test_ask_text_enter_accepts_the_default():
    console = make_console()
    assert ask_text(console, "Name?", default="snake", input_fn=scripted_input([""])) == "snake"


def test_ask_text_returns_typed_value():
    console = make_console()
    assert ask_text(console, "Name?", input_fn=scripted_input(["  pocket-api "])) == "pocket-api"


def test_ask_text_rejects_empty_without_default():
    console = make_console()
    result = ask_text(console, "Name?", input_fn=scripted_input(["", "x"]))
    assert result == "x"
    assert "type something" in console.export_text().lower()


def test_ask_text_allows_empty_when_permitted():
    console = make_console()
    assert ask_text(console, "Notes?", allow_empty=True, input_fn=scripted_input([""])) == ""


def test_ask_text_validator_rejects_then_accepts():
    console = make_console()

    def validator(value):
        return "Use lowercase only." if value != value.lower() else None

    result = ask_text(console, "Name?", validator=validator, input_fn=scripted_input(["Nope", "ok"]))
    assert result == "ok"
    assert "Use lowercase only." in console.export_text()


def test_ask_text_validator_runs_on_the_default_too():
    console = make_console()
    calls = []

    def validator(value):
        calls.append(value)
        return None

    ask_text(console, "Name?", default="snake", validator=validator, input_fn=scripted_input([""]))
    assert calls == ["snake"]


def test_ask_text_shows_placeholder():
    console = make_console()
    ask_text(console, "Name?", default="a", placeholder="my-cool-app", input_fn=scripted_input([""]))
    assert "my-cool-app" in console.export_text()


def test_ask_text_help_then_answer():
    console = make_console()
    result = ask_text(
        console, "Name?", input_fn=scripted_input(["?", "zed"]), help_text="Letters and dashes."
    )
    assert result == "zed"
    assert "Letters and dashes." in console.export_text()


def test_ask_text_back_raises_go_back():
    console = make_console()
    with pytest.raises(GoBack):
        ask_text(console, "Name?", input_fn=scripted_input(["back"]))


def test_ask_text_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_text(console, "Name?", input_fn=scripted_input(["quit"]))


def test_ask_text_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_text(console, "Name?", input_fn=boom_eof)


@pytest.mark.parametrize("width", WIDTHS)
def test_ask_text_render_fits_every_width(width):
    console = make_console(width)
    ask_text(
        console,
        "What should I call this project? Short names travel better.",
        default="pocket-snake-with-a-long-default-name",
        placeholder="my-cool-app",
        input_fn=scripted_input([""]),
        help_text="Letters, numbers and dashes.",
    )
    assert_fits(console, width)


# -- ask_yes_no ------------------------------------------------------------


def test_ask_yes_no_enter_takes_the_default():
    console = make_console()
    assert ask_yes_no(console, "Backend?", default=True, input_fn=scripted_input([""])) is True
    assert ask_yes_no(console, "Backend?", default=False, input_fn=scripted_input([""])) is False


@pytest.mark.parametrize("answer", ["1", "y", "Yes", "YEP", "ok"])
def test_ask_yes_no_accepts_affirmatives(answer):
    console = make_console()
    assert ask_yes_no(console, "Backend?", default=False, input_fn=scripted_input([answer])) is True


@pytest.mark.parametrize("answer", ["2", "n", "No", "nope"])
def test_ask_yes_no_accepts_negatives(answer):
    console = make_console()
    assert ask_yes_no(console, "Backend?", default=True, input_fn=scripted_input([answer])) is False


def test_ask_yes_no_garbage_then_valid():
    console = make_console()
    result = ask_yes_no(console, "Backend?", input_fn=scripted_input(["maybe?", "2"]))
    assert result is False
    assert "1 for yes" in console.export_text()


def test_ask_yes_no_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_yes_no(console, "Backend?", input_fn=scripted_input(["q"]))


def test_ask_yes_no_back_raises_go_back():
    console = make_console()
    with pytest.raises(GoBack):
        ask_yes_no(console, "Backend?", input_fn=scripted_input(["b"]))


def test_ask_yes_no_help_then_answer():
    console = make_console()
    result = ask_yes_no(
        console, "Backend?", input_fn=scripted_input(["?", "1"]), help_text="Say yes if unsure."
    )
    assert result is True
    assert "Say yes if unsure." in console.export_text()


def test_ask_yes_no_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_yes_no(console, "Backend?", input_fn=boom_eof)


@pytest.mark.parametrize("width", WIDTHS)
def test_ask_yes_no_render_fits_every_width(width):
    console = make_console(width)
    ask_yes_no(console, "Does this project need its own backend API?", input_fn=scripted_input([""]))
    assert_fits(console, width)


# -- ask_multi -------------------------------------------------------------


def test_ask_multi_parses_comma_list():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["1,3"])) == ["auth", "pay"]


def test_ask_multi_parses_space_list():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["1 3"])) == ["auth", "pay"]


def test_ask_multi_parses_mixed_separators():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["1, 2 3"])) == [
        "auth",
        "db",
        "pay",
    ]


def test_ask_multi_all_selects_everything():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["all"])) == [
        "auth",
        "db",
        "pay",
    ]


def test_ask_multi_none_selects_nothing():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["none"])) == []


def test_ask_multi_empty_returns_defaults():
    console = make_console()
    result = ask_multi(
        console, "Features?", FEATURES, defaults=["db"], input_fn=scripted_input([""])
    )
    assert result == ["db"]


def test_ask_multi_empty_without_defaults_returns_empty_list():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input([""])) == []


def test_ask_multi_marks_defaults_in_the_render():
    console = make_console()
    ask_multi(console, "Features?", FEATURES, defaults=["db"], input_fn=scripted_input([""]))
    text = console.export_text()
    assert "☑" in text or "[x]" in text


def test_ask_multi_accepts_label_prefixes():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["acc pay"])) == [
        "auth",
        "pay",
    ]


def test_ask_multi_dedupes_and_orders_by_declaration():
    console = make_console()
    assert ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["3 1 1"])) == [
        "auth",
        "pay",
    ]


def test_ask_multi_out_of_range_then_valid():
    console = make_console()
    result = ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["1,9", "2"]))
    assert result == ["db"]
    assert "between 1 and 3" in console.export_text()


def test_ask_multi_garbage_then_valid():
    console = make_console()
    result = ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["!!!", "1"]))
    assert result == ["auth"]


def test_ask_multi_back_raises_go_back():
    console = make_console()
    with pytest.raises(GoBack):
        ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["b"]))


def test_ask_multi_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_multi(console, "Features?", FEATURES, input_fn=scripted_input(["q"]))


def test_ask_multi_help_then_answer():
    console = make_console()
    result = ask_multi(
        console, "Features?", FEATURES, input_fn=scripted_input(["?", "2"]), help_text="Pick any."
    )
    assert result == ["db"]
    assert "Pick any." in console.export_text()


def test_ask_multi_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        ask_multi(console, "Features?", FEATURES, input_fn=boom_eof)


def test_ask_multi_with_no_choices_returns_empty_without_reading():
    console = make_console()
    assert ask_multi(console, "Features?", [], input_fn=scripted_input([])) == []


def test_ask_multi_ignores_unknown_defaults():
    console = make_console()
    result = ask_multi(
        console, "Features?", FEATURES, defaults=["nope", "pay"], input_fn=scripted_input([""])
    )
    assert result == ["pay"]


@pytest.mark.parametrize("width", WIDTHS)
def test_ask_multi_render_fits_every_width(width):
    console = make_console(width)
    ask_multi(
        console,
        "Which of these does the project actually need on day one?",
        FEATURES,
        defaults=["db"],
        input_fn=scripted_input(["1,3"]),
        help_text="You can add more later.",
    )
    assert_fits(console, width)


# -- confirm_danger --------------------------------------------------------


def test_confirm_danger_requires_the_word_yes():
    console = make_console()
    assert confirm_danger(console, "Delete src/?", input_fn=scripted_input(["yes"])) is True


def test_confirm_danger_enter_cancels():
    console = make_console()
    assert confirm_danger(console, "Delete src/?", input_fn=scripted_input([""])) is False


@pytest.mark.parametrize("answer", ["n", "no", "NO"])
def test_confirm_danger_explicit_no(answer):
    console = make_console()
    assert confirm_danger(console, "Delete src/?", input_fn=scripted_input([answer])) is False


def test_confirm_danger_reasks_on_garbage():
    console = make_console()
    result = confirm_danger(console, "Delete src/?", input_fn=scripted_input(["sure", "yes"]))
    assert result is True
    assert "Type 'yes'" in console.export_text()


def test_confirm_danger_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        confirm_danger(console, "Delete src/?", input_fn=scripted_input(["q"]))


def test_confirm_danger_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        confirm_danger(console, "Delete src/?", input_fn=boom_eof)


@pytest.mark.parametrize("width", WIDTHS)
def test_confirm_danger_render_fits_every_width(width):
    console = make_console(width)
    confirm_danger(
        console,
        "This deletes every file under /data/data/com.termux/files/home/projects/demo.",
        input_fn=scripted_input([""]),
    )
    assert_fits(console, width)


# -- pause -----------------------------------------------------------------


def test_pause_returns_none_on_enter():
    console = make_console()
    assert pause(console, input_fn=scripted_input([""])) is None


def test_pause_shows_its_message():
    console = make_console()
    pause(console, message="Read this, then continue", input_fn=scripted_input([""]))
    assert "Read this" in console.export_text()


def test_pause_quit_raises_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        pause(console, input_fn=scripted_input(["q"]))


def test_pause_eof_becomes_quit_app():
    console = make_console()
    with pytest.raises(QuitApp):
        pause(console, input_fn=boom_eof)


@pytest.mark.parametrize("width", WIDTHS)
def test_pause_render_fits_every_width(width):
    console = make_console(width)
    pause(console, message="Press Enter when you have read the plan above", input_fn=scripted_input([""]))
    assert_fits(console, width)


# -- layout injection and env ---------------------------------------------


def test_prompts_accept_an_explicit_layout():
    console = make_console(100)
    layout = Layout.detect(width=32)
    ask_choice(console, "Kind?", KINDS, default="web", layout=layout, input_fn=scripted_input([""]))
    for line in console.export_text().splitlines():
        assert cell_len(line) <= 32


def test_prompts_degrade_to_ascii_without_unicode(monkeypatch):
    monkeypatch.setenv("ANYWHERE_ASCII", "1")
    console = make_console(80)
    ask_choice(console, "Kind?", KINDS, default="web", input_fn=scripted_input(["zz", ""]))
    text = console.export_text()
    assert "·" not in text
    assert "→" not in text


def test_prompt_errors_never_leak_a_traceback():
    console = make_console()
    ask_choice(console, "Kind?", KINDS, input_fn=scripted_input(["???!!!", "1"]))
    text = console.export_text()
    assert "Traceback" not in text
    assert "Kind?" in text
