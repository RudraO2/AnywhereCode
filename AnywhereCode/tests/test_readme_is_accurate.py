"""The README makes checkable claims. This checks them.

Documentation drifts silently: a template gets added and the scaffold table
still lists five, a recipe lands and the count still says sixteen. Nothing
fails, and the first person to notice is a user who trusted the table. Every
assertion here is about a fact the code already knows.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

import anyplace
from anyplace.cli.main import cli
from anyplace.core.recipes import RECIPES


PACKAGE_DIR = pathlib.Path(anyplace.__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

#: The README is the repository landing page, one level above the package dir.
README = PACKAGE_DIR.parent.parent / "README.md"

NUMBER_WORDS = {
    5: "five",
    6: "six",
    7: "seven",
    15: "Fifteen",
    16: "Sixteen",
    17: "Seventeen",
    18: "Eighteen",
}


@pytest.fixture(scope="module")
def readme():
    if not README.exists():  # pragma: no cover - layout guard
        pytest.skip("README.md is not next to the package")
    return README.read_text(encoding="utf-8")


def template_metadata():
    out = {}
    for directory in sorted(TEMPLATES_DIR.iterdir()):
        structure = directory / "structure.json"
        if directory.is_dir() and structure.exists():
            out[directory.name] = json.loads(structure.read_text(encoding="utf-8"))
    return out


# ---------------------------------------------------------------------------
# The fixture itself
# ---------------------------------------------------------------------------


def test_readme_exists_and_is_substantial(readme):
    assert len(readme) > 2000, "README looks truncated"


def test_template_metadata_is_discoverable():
    assert len(template_metadata()) >= 5


# ---------------------------------------------------------------------------
# Scaffolds
# ---------------------------------------------------------------------------


def test_every_shipped_scaffold_appears_in_the_readme(readme):
    for name, data in template_metadata().items():
        assert data["display_name"] in readme, (
            "scaffold %r (%s) is missing from the README table"
            % (name, data["display_name"])
        )


def test_the_readme_does_not_advertise_a_scaffold_that_does_not_ship(readme):
    """Catches a row left behind after a template is removed."""
    shipped = set(d["display_name"] for d in template_metadata().values())

    table_rows = re.findall(
        r"^\| ([^|]+?) \| .*? \| (beginner|intermediate|advanced) \|", readme, re.M
    )
    listed = set(name.strip() for name, _ in table_rows)

    assert listed, "the scaffold table did not parse -- has its shape changed?"
    assert listed <= shipped, "README lists scaffolds that do not ship: %s" % (
        sorted(listed - shipped),
    )


def test_the_scaffold_count_in_prose_matches_reality(readme):
    count = len(template_metadata())
    word = NUMBER_WORDS.get(count)
    assert word, "add %d to NUMBER_WORDS" % count
    assert "%s scaffolds" % word in readme, (
        "README should say %r scaffolds; there are %d" % (word, count)
    )


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


def test_the_recipe_count_in_prose_matches_reality(readme):
    count = len(RECIPES)
    word = NUMBER_WORDS.get(count)
    assert word, "add %d to NUMBER_WORDS" % count
    assert "%s one-tap starting points" % word in readme, (
        "README should say %r one-tap starting points; there are %d" % (word, count)
    )


def test_every_recipe_is_named_in_the_readme(readme):
    # Whitespace-normalised: the list is prose, so a name can wrap a line.
    lowered = " ".join(readme.lower().split())
    for recipe in RECIPES:
        title = " ".join(recipe.title.lower().split())
        assert title in lowered, "recipe %r is missing from the README list" % recipe.title


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def code_spans(readme):
    """Fenced blocks and inline code -- the places a command is actually shown.

    Prose is excluded on purpose: the intro sentence "…or anywhere else Python
    runs" is not advertising an `anywhere else` command.
    """
    fenced = re.findall(r"```.*?\n(.*?)```", readme, re.S)
    inline = re.findall(r"`([^`\n]+)`", readme)
    return fenced + inline


def test_code_spans_finds_the_command_examples(readme):
    joined = "\n".join(code_spans(readme))
    assert "anywhere doctor" in joined
    assert "anywhere else" not in joined


def test_every_command_the_readme_shows_exists(readme):
    known = set(cli.commands)
    shown = set()
    for span in code_spans(readme):
        shown.update(re.findall(r"\banywhere ([a-z][a-z-]*)", span))

    # `anywhere --help` and bare `anywhere` produce no capture; --auto etc. are
    # flags, not commands, and start with a dash so the pattern skips them.
    unknown = shown - known
    assert not unknown, "README shows commands that do not exist: %s" % sorted(unknown)


def test_the_command_check_would_catch_an_invented_command(readme):
    known = set(cli.commands)
    shown = set(re.findall(r"\banywhere ([a-z][a-z-]*)", "run `anywhere teleport` now"))
    assert shown - known == {"teleport"}


def test_the_readme_mentions_the_commands_a_new_user_needs(readme):
    for name in ("configure", "doctor", "new", "open"):
        assert "anywhere %s" % name in readme


# ---------------------------------------------------------------------------
# Safety section
# ---------------------------------------------------------------------------


def safety_section(readme):
    body = readme[readme.index("## Safety") :]
    return body[: body.index("\n## ")] if "\n## " in body else body


def test_the_safety_section_describes_an_allowlist(readme):
    """The gate was a denylist once; the README must not still say so."""
    assert "allowlist" in safety_section(readme).lower()


def test_the_safety_section_does_not_claim_a_blocklist(readme):
    assert "checked against a blocklist" not in safety_section(readme).lower()


def test_tools_the_readme_names_as_refused_really_are(readme):
    from anyplace.core.agent_executor import ALLOWED_PROGRAMS

    for tool in ("rm", "sudo", "bash", "sh", "curl"):
        assert tool not in ALLOWED_PROGRAMS, "%r is named as refused but is allowed" % tool


def test_tools_the_readme_names_as_allowed_really_are(readme):
    from anyplace.core.agent_executor import ALLOWED_PROGRAMS

    for tool in ("npm", "pip", "cargo", "go", "git"):
        assert tool in ALLOWED_PROGRAMS, "README says %r is allowed; it is not" % tool
        assert tool in safety_section(readme)


def test_commands_the_readme_says_are_refused_really_are():
    from anyplace.core.agent_executor import is_command_safe

    for cmd in (
        ["git", "push", "--force"],
        ["chmod", "-R", "777", "."],
        ["python3", "-c", "print(1)"],
        ["npm", "run", "clean", "--", "rm -rf /"],
        ["rm", "-rf", "/"],
        ["sudo", "apt", "install", "x"],
    ):
        assert is_command_safe(cmd)[0] is False, "%r should be refused" % (cmd,)


# ---------------------------------------------------------------------------
# The opening
#
# The first screen of the README is the positioning: who this is for, and why
# the alternatives don't fit. Its factual claims are as checkable as the
# scaffold table's, and they rot the same way.
# ---------------------------------------------------------------------------


def opening(readme):
    """Everything above the Install section."""
    return readme[: readme.index("## Install")]


def test_the_opening_says_who_it_is_for(readme):
    assert "main computer is a phone" in opening(readme)


def test_the_opening_names_a_real_recipe_as_the_friendly_example(readme):
    """It contrasts a recipe title with a scaffold id -- both must be real."""
    from anyplace.core.recipes import RECIPES

    head = opening(readme)
    titles = set(r.title for r in RECIPES)
    quoted = set(re.findall(r'"([A-Z][a-z]+(?: [a-z]+)*)"', head))
    assert quoted & titles, (
        "the opening should name a real recipe; found %s" % sorted(quoted)
    )


def test_the_opening_contrasts_it_with_a_real_template_id(readme):
    assert "mobile-expo-rn" in opening(readme)
    assert "mobile-expo-rn" in template_metadata()


def test_the_width_count_in_the_opening_matches_the_suite(readme):
    """'eleven widths' has to be however many the suite actually runs."""
    from tests.test_rendered_output_fits import WIDTHS

    words = {
        9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    }
    word = words.get(len(WIDTHS))
    assert word, "add %d to the word map" % len(WIDTHS)
    assert "%s widths" % word in opening(readme), (
        "opening should say %r widths; the suite runs %d" % (word, len(WIDTHS))
    )


def test_scaffolds_the_opening_calls_on_device_really_are(readme):
    head = opening(readme)
    metadata = template_metadata()
    by_display = dict((d["display_name"], d) for d in metadata.values())

    # "React, Express and FastAPI projects build and run on-device."
    for display in ("React web app", "Express API", "FastAPI API"):
        assert by_display[display]["mobile_friendly"] is True, (
            "%s is described as on-device but is not marked mobile_friendly" % display
        )
    assert "on-device" in head


def test_scaffolds_the_opening_defers_to_ci_really_are_heavy(readme):
    metadata = template_metadata()
    by_display = dict((d["display_name"], d) for d in metadata.values())

    # "Next.js, Expo and native Android are all marked build on desktop or CI"
    for display in ("Next.js app", "Expo mobile app", "Android (Kotlin)"):
        assert by_display[display]["mobile_friendly"] is False, (
            "%s is described as desktop/CI-only but is marked mobile_friendly" % display
        )


def test_the_opening_links_resolve_to_real_headings(readme):
    """A dead anchor in the first screen is a bad first impression."""
    headings = set()
    for line in readme.splitlines():
        if line.startswith("## "):
            slug = line[3:].strip().lower()
            slug = re.sub(r"[^\w\s-]", "", slug).replace(" ", "-")
            headings.add(slug)

    for anchor in re.findall(r"\]\(#([\w-]+)\)", opening(readme)):
        assert anchor in headings, "opening links to #%s, which is not a heading" % anchor


def test_the_opening_does_not_repeat_the_small_screen_section(readme):
    """
    The opening pitches; the section explains. When the opening started
    re-listing the mechanics (tofu emoji, stacked tables, defaults) the two
    drifted apart and disagreed on how many widths were tested.
    """
    head = opening(readme)
    for mechanic in ("tofu", "ANYWHERE_THEME", "Label: value"):
        assert mechanic not in head, (
            "%r belongs in the small-screen section, not the opening" % mechanic
        )
