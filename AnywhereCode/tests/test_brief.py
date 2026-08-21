"""Tests for anyplace.core.brief."""

import pytest

from anyplace.core.brief import ProjectBrief


def rich_brief():
    return ProjectBrief(
        name="runlog",
        idea="a place to log my runs and see a weekly chart",
        project_kind="fullstack",
        audience="me and a few running friends",
        features=["auth", "storage", "search"],
        needs_backend=True,
        needs_auth=True,
        database="postgres",
        styling="tailwind",
        complexity="standard",
        deploy_target="cloud",
        notes="must keep working with no signal",
        answers={"project_name": "runlog"},
    )


# --------------------------------------------------------------------------
# to_prompt
# --------------------------------------------------------------------------

def test_to_prompt_includes_idea_and_name_for_rich_brief():
    text = rich_brief().to_prompt()
    assert "runlog" in text
    assert "log my runs" in text
    assert "PROJECT BRIEF" in text


def test_to_prompt_derives_users_table_when_auth_and_postgres():
    text = rich_brief().to_prompt()
    assert "users table" in text
    assert "session" in text.lower()
    assert "PostgreSQL" in text


def test_to_prompt_lists_every_requested_feature_in_plain_words():
    text = rich_brief().to_prompt()
    assert "accounts & login" in text
    assert "search" in text


def test_to_prompt_states_scope_guidance_for_ambitious_brief():
    brief = rich_brief()
    brief.complexity = "ambitious"
    text = brief.to_prompt()
    assert "ambitious" in text
    assert "tests for the core logic" in text


def test_to_prompt_handles_empty_brief_without_raising():
    text = ProjectBrief().to_prompt()
    assert text.strip()
    assert "not described the project yet" in text
    assert "None" not in text


def test_to_prompt_defaults_to_sqlite_when_storage_implied_but_undecided():
    brief = ProjectBrief(idea="save my notes", features=["storage"])
    text = brief.to_prompt()
    assert "SQLite" in text


def test_to_prompt_respects_explicit_no_database():
    brief = ProjectBrief(idea="a calculator", database="none")
    text = brief.to_prompt()
    assert "no database" in text
    assert "do not add an ORM" in text


def test_to_prompt_mentions_phone_constraints():
    assert "Termux" in rich_brief().to_prompt()
    assert "Termux" in ProjectBrief().to_prompt()


def test_to_prompt_collapses_multiline_free_text():
    brief = ProjectBrief(idea="line one\n   line two", complexity="simple")
    assert "line one line two" in brief.to_prompt()


# --------------------------------------------------------------------------
# to_dict / from_dict
# --------------------------------------------------------------------------

def test_round_trip_to_dict_from_dict_preserves_every_field():
    original = rich_brief()
    restored = ProjectBrief.from_dict(original.to_dict())
    assert restored.to_dict() == original.to_dict()


def test_from_dict_keeps_unknown_extra_keys_in_answers():
    data = rich_brief().to_dict()
    data["future_field"] = "keep me"
    data["another"] = 7
    restored = ProjectBrief.from_dict(data)
    assert restored.answers["future_field"] == "keep me"
    assert restored.answers["another"] == 7
    assert restored.name == "runlog"


def test_from_dict_does_not_let_extras_clobber_real_answers():
    data = {"answers": {"project_name": "real"}, "project_name": "extra"}
    restored = ProjectBrief.from_dict(data)
    assert restored.answers["project_name"] == "real"


def test_from_dict_returns_default_for_non_dict_input():
    for junk in (None, [], "nope", 42):
        assert ProjectBrief.from_dict(junk).is_empty()


def test_from_dict_coerces_wrong_types_instead_of_raising():
    restored = ProjectBrief.from_dict(
        {
            "name": 123,
            "features": "auth, storage",
            "needs_backend": "yes",
            "needs_auth": 0,
            "answers": "not a dict",
            "complexity": "",
        }
    )
    assert restored.name == "123"
    assert restored.features == ["auth", "storage"]
    assert restored.needs_backend is True
    assert restored.needs_auth is False
    assert restored.answers == {}
    assert restored.complexity == "simple"


def test_from_dict_missing_keys_fall_back_to_defaults():
    restored = ProjectBrief.from_dict({"name": "x"})
    assert restored.name == "x"
    assert restored.features == []
    assert restored.complexity == "simple"


# --------------------------------------------------------------------------
# summary_pairs
# --------------------------------------------------------------------------

def test_summary_pairs_truncates_long_free_text():
    brief = ProjectBrief(idea="x" * 200, name="n")
    pairs = dict(brief.summary_pairs())
    assert pairs["Idea"].endswith("...")
    assert len(pairs["Idea"]) <= 38


def test_summary_pairs_truncates_on_a_word_boundary():
    brief = ProjectBrief(
        idea="a really quite long description of a thing that keeps going on"
    )
    value = dict(brief.summary_pairs())["Idea"]
    assert value.endswith("...")
    assert "  " not in value


def test_summary_pairs_values_fit_a_phone_screen():
    brief = rich_brief()
    brief.idea = "y" * 300
    brief.notes = "z" * 300
    brief.audience = "w" * 300
    for label, value in brief.summary_pairs():
        assert len(label) <= 12
        assert len(value) <= 38, (label, value)


def test_summary_pairs_omits_blank_optional_fields():
    labels = [label for label, _ in ProjectBrief().summary_pairs()]
    assert "Idea" not in labels
    assert "Notes" not in labels
    assert "Name" in labels


def test_summary_pairs_shows_placeholder_name_when_unnamed():
    assert dict(ProjectBrief().summary_pairs())["Name"] == "Untitled project"


def test_summary_pairs_renders_booleans_as_yes_no():
    pairs = dict(rich_brief().summary_pairs())
    assert pairs["Backend"] == "yes"
    assert pairs["Accounts"] == "yes"
    assert dict(ProjectBrief().summary_pairs())["Accounts"] == "no"


# --------------------------------------------------------------------------
# is_empty
# --------------------------------------------------------------------------

def test_is_empty_true_for_a_default_brief():
    assert ProjectBrief().is_empty() is True


def test_is_empty_true_when_complexity_is_the_default_simple():
    assert ProjectBrief(complexity="simple").is_empty() is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "x"},
        {"idea": "x"},
        {"project_kind": "web"},
        {"features": ["auth"]},
        {"needs_backend": True},
        {"needs_auth": True},
        {"database": "sqlite"},
        {"complexity": "standard"},
        {"notes": "x"},
    ],
)
def test_is_empty_false_when_any_single_field_is_set(kwargs):
    assert ProjectBrief(**kwargs).is_empty() is False


def test_is_empty_ignores_whitespace_only_text():
    assert ProjectBrief(name="   ", idea="\n").is_empty() is True


# --------------------------------------------------------------------------
# derived helpers
# --------------------------------------------------------------------------

def test_implies_backend_true_for_auth_feature_without_explicit_flag():
    assert ProjectBrief(features=["auth"]).implies_backend() is True


def test_implies_backend_false_for_cosmetic_features_only():
    assert ProjectBrief(features=["darkmode"]).implies_backend() is False


def test_implies_storage_true_for_uploads():
    assert ProjectBrief(features=["uploads"]).implies_storage() is True
