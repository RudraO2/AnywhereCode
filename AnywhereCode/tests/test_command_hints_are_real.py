"""Every command we tell the user to type must actually exist.

A wrong hint is worse than no hint: the user is already stuck, they type what
we told them to, and the shell says "no such command". That is the moment
people give up on a tool -- and on a phone, where retyping is expensive, it is
worse still.

This suite walks the strings the CLI shows people (doctor fixes, recovery
suggestions, error bodies) and checks every `anywhere <subcommand>` in them
against the real click command tree. It caught `anyplace --configure`, a flag
that never existed, in five separate doctor checks.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from anyplace.cli import error_handler as eh
from anyplace.cli.main import cli


#: `anywhere foo`, `anyplace foo` -- captures the subcommand that follows.
HINT_RE = re.compile(r"\b(?:anywhere|anyplace)\b(?:\s+(--?[a-z-]+|[a-z][a-z-]*))?")


@pytest.fixture(scope="module")
def repo_root():
    import anyplace

    return pathlib.Path(anyplace.__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def known_commands():
    return set(cli.commands)


@pytest.fixture(scope="module")
def known_root_flags():
    flags = set()
    for param in cli.params:
        flags.update(param.opts)
        flags.update(param.secondary_opts)
    return flags


def hints_in(text):
    """Every (whole match, token) pair where our own CLI is named in `text`."""
    return [(m.group(0), m.group(1)) for m in HINT_RE.finditer(text or "")]


def assert_hint_is_real(text, known_commands, known_root_flags, source):
    for whole, token in hints_in(text):
        if token is None:
            # Bare "anywhere" -- launching the tool with no subcommand is valid.
            continue
        if token.startswith("-"):
            assert token in known_root_flags, (
                "%s suggests %r, but %s is not a flag on the root command"
                % (source, whole, token)
            )
        else:
            assert token in known_commands, (
                "%s suggests %r, but there is no `anywhere %s` command"
                % (source, whole, token)
            )


# ---------------------------------------------------------------------------
# The regex itself -- a hint checker that matches nothing would pass silently
# ---------------------------------------------------------------------------


def test_hint_regex_finds_a_subcommand():
    assert hints_in("then run: anywhere doctor") == [("anywhere doctor", "doctor")]


def test_hint_regex_finds_a_flag():
    assert hints_in("try anyplace --configure") == [("anyplace --configure", "--configure")]


def test_hint_regex_allows_a_bare_invocation():
    assert hints_in("just type anywhere") == [("anywhere", None)]


def test_hint_regex_ignores_unrelated_prose():
    assert hints_in("you can code anywhere, anytime") == [("anywhere", None)]


def test_the_checker_rejects_a_command_that_does_not_exist(known_commands, known_root_flags):
    with pytest.raises(AssertionError):
        assert_hint_is_real(
            "run: anywhere teleport", known_commands, known_root_flags, "a test"
        )


def test_the_checker_rejects_a_flag_that_does_not_exist(known_commands, known_root_flags):
    with pytest.raises(AssertionError):
        assert_hint_is_real(
            "run: anyplace --configure", known_commands, known_root_flags, "a test"
        )


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_every_doctor_fix_hint_names_a_real_command(known_commands, known_root_flags):
    from anyplace.core import doctor as doc

    report = doc.run_all()
    for check in report.checks:
        for text in (check.fix, check.detail, check.title):
            assert_hint_is_real(
                text, known_commands, known_root_flags, "doctor check %r" % check.title
            )


# ---------------------------------------------------------------------------
# Static sweep
#
# Running the doctor only exercises the branches this machine happens to take:
# a device with git installed never reaches the "install git" hint. So we also
# read every string literal in the user-facing modules, which covers branches
# no single machine can reach.
# ---------------------------------------------------------------------------


HINT_MODULES = [
    "anyplace/core/doctor.py",
    "anyplace/cli/error_handler.py",
    "anyplace/config/api_manager.py",
    "anyplace/cli/main.py",
    "anyplace/cli/flows.py",
    "anyplace/cli/config_wizard.py",
    "anyplace/cli/doctor_screen.py",
    "anyplace/cli/recipes_screen.py",
    "anyplace/cli/interview_screen.py",
    "anyplace/cli/app.py",
]


def string_literals(path):
    """Every string constant in a module, including f-string literal parts."""
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


@pytest.mark.parametrize("module_path", HINT_MODULES)
def test_no_module_advertises_a_command_that_does_not_exist(
    module_path, known_commands, known_root_flags, repo_root
):
    path = repo_root / module_path
    if not path.exists():  # pragma: no cover - keeps the list forgiving
        pytest.skip("%s does not ship" % module_path)

    for lineno, text in string_literals(path):
        assert_hint_is_real(
            text,
            known_commands,
            known_root_flags,
            "%s:%s" % (module_path, lineno),
        )


def test_the_static_sweep_actually_reads_something(repo_root):
    literals = list(string_literals(repo_root / "anyplace/core/doctor.py"))
    assert len(literals) > 50, "the AST sweep found almost nothing -- is it wired up?"
    assert any(hints_in(text) for _, text in literals), (
        "doctor.py never names the CLI, which means this sweep proves nothing"
    )


# ---------------------------------------------------------------------------
# error_handler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        eh.ConfigError("No api_key configured"),
        eh.ConfigError("Template 'x' not found"),
        eh.APIError("401 Unauthorized"),
        eh.APIError("Connection failed"),
        eh.APIError("Request timed out"),
        eh.APIError("rate_limit exceeded"),
        eh.FileSystemError("No space left on device"),
        eh.FileSystemError("Permission denied"),
        eh.GenerationError("template missing"),
        eh.GenerationError("Git not installed or not in PATH"),
        eh.GenerationError("Circular dependency detected"),
        RuntimeError("something else entirely"),
    ],
    ids=lambda e: "%s:%s" % (type(e).__name__, str(e)[:24]),
)
def test_recovery_suggestions_name_real_commands(error, known_commands, known_root_flags):
    suggestion = eh.get_recovery_suggestion(error)
    if suggestion is None:
        return
    assert_hint_is_real(
        suggestion, known_commands, known_root_flags, "recovery for %r" % error
    )


@pytest.mark.parametrize(
    "error",
    [
        eh.ConfigError("No api_key configured"),
        eh.APIError("401 Unauthorized"),
        eh.FileSystemError("Permission denied"),
        eh.GenerationError("Circular dependency detected"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_error_bodies_name_real_commands(error, known_commands, known_root_flags):
    assert_hint_is_real(
        eh.describe(error), known_commands, known_root_flags, "describe(%r)" % error
    )


# ---------------------------------------------------------------------------
# The command tree itself
# ---------------------------------------------------------------------------


def test_the_commands_the_docs_lean_on_all_exist(known_commands):
    # These are named in the README, the doctor output and the empty states.
    for name in ("configure", "doctor", "new", "start", "templates", "recipes", "run"):
        assert name in known_commands, "`anywhere %s` is referenced but missing" % name


def test_every_command_has_a_help_line(known_commands):
    for name, command in cli.commands.items():
        assert (command.help or command.short_help), "`%s` has no help text" % name
