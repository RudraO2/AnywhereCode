"""Tests for anyplace.core.interview."""

import itertools

import pytest

from anyplace.core.interview import (
    EXPERT,
    GUIDED,
    QUESTION_BANK,
    QUICK,
    Interview,
    Question,
    get_question,
)

CANONICAL_IDS = [
    "project_name",
    "idea",
    "project_kind",
    "audience",
    "features",
    "needs_backend",
    "needs_auth",
    "database",
    "styling",
    "complexity",
    "deploy_target",
    "notes",
]


def ids_of(questions):
    return [q.id for q in questions]


# --------------------------------------------------------------------------
# Question bank shape
# --------------------------------------------------------------------------

def test_question_bank_uses_exactly_the_canonical_ids():
    assert ids_of(QUESTION_BANK) == CANONICAL_IDS


def test_question_bank_ids_are_unique():
    bank_ids = ids_of(QUESTION_BANK)
    assert len(bank_ids) == len(set(bank_ids))


def test_every_question_has_a_known_kind_and_help_text():
    for question in QUESTION_BANK:
        assert question.kind in ("choice", "text", "yesno", "multi"), question.id
        assert question.help, question.id
        assert question.text.strip(), question.id


def test_choice_and_multi_questions_have_options():
    for question in QUESTION_BANK:
        if question.kind in ("choice", "multi"):
            assert question.options, question.id
            assert all(isinstance(v, str) and label for v, label in question.options)


def test_project_kind_asks_in_plain_words_not_frameworks():
    labels = " ".join(label for _, label in get_question("project_kind").options).lower()
    assert "website" in labels
    assert "phone" in labels
    assert "not sure" in labels
    for framework in ("react", "next", "django", "express", "vue"):
        assert framework not in labels


def test_features_list_fits_a_phone_screen():
    options = get_question("features").options
    assert 8 <= len(options) <= 10
    assert all(len(label) <= 24 for _, label in options)


def test_complexity_options_are_phrased_as_effort_not_jargon():
    labels = [label for _, label in get_question("complexity").options]
    assert labels == ["Keep it minimal", "Standard", "Go big"]


def test_get_question_returns_none_for_unknown_id():
    assert get_question("nope") is None


def test_question_applies_defaults_to_true_without_a_predicate():
    assert Question(id="x", text="t", kind="text").applies({}) is True


def test_question_with_a_broken_predicate_is_skipped_not_fatal():
    def boom(answers):
        raise RuntimeError("bad predicate")

    assert Question(id="x", text="t", kind="text", when=boom).applies({}) is False


# --------------------------------------------------------------------------
# Mode budgets
# --------------------------------------------------------------------------

def test_expert_mode_asks_exactly_name_and_idea():
    assert ids_of(Interview(EXPERT).applicable()) == ["project_name", "idea"]


def test_quick_mode_asks_at_most_four_questions():
    interview = Interview(QUICK)
    assert len(interview.applicable()) <= 4


def test_quick_mode_question_set_is_stable_while_answering():
    interview = Interview(QUICK)
    assert ids_of(interview.applicable()) == [
        "project_name",
        "idea",
        "project_kind",
        "complexity",
    ]
    interview.answer("project_kind", "fullstack")
    assert len(interview.applicable()) <= 4


def test_guided_mode_stays_within_six_to_ten_questions_for_every_branch():
    kinds = ["", "web", "mobile", "backend", "fullstack", "cli", "unsure"]
    feature_sets = [
        [],
        ["auth"],
        ["storage"],
        ["darkmode"],
        ["auth", "payments", "search", "admin", "realtime"],
    ]
    backend_answers = [None, True, False]
    complexities = ["simple", "standard", "ambitious"]
    for kind, features, backend, complexity in itertools.product(
        kinds, feature_sets, backend_answers, complexities
    ):
        answers = {"features": features, "complexity": complexity}
        if kind:
            answers["project_kind"] = kind
        if backend is not None:
            answers["needs_backend"] = backend
        interview = Interview(GUIDED)
        interview.prefill(answers)
        count = len(interview.applicable())
        assert 6 <= count <= 10, (kind, features, backend, count)


def test_guided_mode_starts_within_budget():
    total = Interview(GUIDED).progress()[1]
    assert 6 <= total <= 10


def test_unknown_mode_raises_a_clear_error():
    with pytest.raises(ValueError, match="Unknown interview mode"):
        Interview("telepathic")


def test_mode_property_is_normalised():
    assert Interview("GUIDED").mode == GUIDED


# --------------------------------------------------------------------------
# Branching
# --------------------------------------------------------------------------

def test_database_is_not_asked_before_any_storage_signal():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    assert "database" not in ids_of(interview.applicable())


def test_database_is_asked_once_a_server_is_needed():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    interview.answer("needs_backend", True)
    assert "database" in ids_of(interview.applicable())


def test_database_is_asked_when_features_imply_storage():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    interview.answer("features", ["uploads"])
    assert "database" in ids_of(interview.applicable())


def test_needs_backend_is_not_asked_for_a_backend_project():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "backend")
    assert "needs_backend" not in ids_of(interview.applicable())


def test_styling_is_asked_only_for_things_with_a_screen():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "backend")
    assert "styling" not in ids_of(interview.applicable())
    interview.answer("project_kind", "web")
    assert "styling" in ids_of(interview.applicable())


def test_deploy_target_is_asked_only_when_styling_is_not():
    for kind in ("web", "mobile", "backend", "cli", "unsure", "fullstack"):
        interview = Interview(GUIDED)
        interview.answer("project_kind", kind)
        asked = ids_of(interview.applicable())
        assert ("styling" in asked) != ("deploy_target" in asked), kind


def test_notes_is_never_asked_but_can_be_prefilled():
    for mode in (QUICK, GUIDED, EXPERT):
        assert "notes" not in ids_of(Interview(mode).applicable())
    interview = Interview(GUIDED)
    interview.prefill({"notes": "no internet"})
    assert interview.to_brief().notes == "no internet"


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------

def test_picking_accounts_feature_pre_answers_needs_auth():
    interview = Interview(GUIDED)
    interview.answer("features", ["auth"])
    assert interview.answers["needs_auth"] is True
    assert "needs_auth" not in ids_of(interview.applicable())


def test_needs_auth_is_still_asked_without_the_accounts_feature():
    interview = Interview(GUIDED)
    interview.answer("features", ["darkmode"])
    assert "needs_auth" in ids_of(interview.applicable())
    assert "needs_auth" not in interview.answers


def test_backend_project_kind_pre_answers_needs_backend():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "fullstack")
    assert interview.answers["needs_backend"] is True


def test_server_shaped_features_pre_answer_needs_backend():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    interview.answer("features", ["payments"])
    assert interview.answers["needs_backend"] is True


def test_explicit_needs_backend_answer_is_not_overwritten_by_inference():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    interview.answer("needs_backend", False)
    interview.answer("features", ["storage"])
    assert interview.answers["needs_backend"] is False


# --------------------------------------------------------------------------
# answer() validation
# --------------------------------------------------------------------------

def test_answer_with_an_unknown_id_raises_a_clear_error():
    with pytest.raises(ValueError, match="Unknown question id"):
        Interview(GUIDED).answer("favourite_colour", "blue")


def test_answer_with_an_invalid_choice_lists_the_valid_options():
    with pytest.raises(ValueError, match="Valid options"):
        Interview(GUIDED).answer("project_kind", "django")


def test_answer_multi_with_a_non_sequence_raises_type_error():
    with pytest.raises(TypeError):
        Interview(GUIDED).answer("features", 5)


def test_answer_multi_accepts_a_comma_separated_string():
    interview = Interview(GUIDED)
    interview.answer("features", "auth, storage")
    assert interview.answers["features"] == ["auth", "storage"]


def test_answer_multi_rejects_an_unknown_option():
    with pytest.raises(ValueError, match="no option"):
        Interview(GUIDED).answer("features", ["telepathy"])


def test_answer_multi_deduplicates_and_accepts_none_keyword():
    interview = Interview(GUIDED)
    interview.answer("features", ["auth", "auth"])
    assert interview.answers["features"] == ["auth"]
    interview.answer("features", "none")
    assert interview.answers["features"] == []


def test_answer_yesno_accepts_human_spellings():
    interview = Interview(GUIDED)
    interview.answer("needs_backend", "yes")
    assert interview.answers["needs_backend"] is True
    interview.answer("needs_backend", "n")
    assert interview.answers["needs_backend"] is False


def test_answer_yesno_rejects_gibberish():
    with pytest.raises(ValueError, match="yes or no"):
        Interview(GUIDED).answer("needs_backend", "maybe")


def test_answer_text_strips_whitespace():
    interview = Interview(GUIDED)
    interview.answer("project_name", "  my-app \n")
    assert interview.answers["project_name"] == "my-app"


def test_answers_property_returns_a_copy():
    interview = Interview(GUIDED)
    interview.answer("project_name", "x")
    snapshot = interview.answers
    snapshot["project_name"] = "tampered"
    assert interview.answers["project_name"] == "x"


# --------------------------------------------------------------------------
# next_question / progress / is_complete
# --------------------------------------------------------------------------

def test_next_question_walks_the_bank_in_order():
    interview = Interview(GUIDED)
    assert interview.next_question().id == "project_name"
    interview.answer("project_name", "x")
    assert interview.next_question().id == "idea"


def test_next_question_returns_none_when_everything_is_answered():
    interview = Interview(EXPERT)
    interview.answer("project_name", "x")
    interview.answer("idea", "y")
    assert interview.next_question() is None


def test_progress_counts_only_applicable_questions():
    interview = Interview(EXPERT)
    assert interview.progress() == (0, 2)
    interview.answer("project_name", "x")
    assert interview.progress() == (1, 2)


def test_progress_total_tracks_branch_changes():
    interview = Interview(GUIDED)
    interview.answer("project_kind", "web")
    before = interview.progress()[1]
    interview.answer("needs_backend", True)   # opens the database branch
    after = interview.progress()[1]
    assert after == before + 1
    assert interview.progress()[0] == 2


def test_progress_answered_never_exceeds_total():
    interview = Interview(GUIDED)
    for qid, value in [
        ("project_name", "x"),
        ("idea", "y"),
        ("project_kind", "backend"),
        ("features", ["auth"]),
    ]:
        interview.answer(qid, value)
        answered, total = interview.progress()
        assert 0 <= answered <= total


def test_is_complete_false_until_required_questions_are_answered():
    interview = Interview(GUIDED)
    assert interview.is_complete() is False
    interview.answer("project_name", "x")
    assert interview.is_complete() is False


def test_is_complete_ignores_optional_questions():
    interview = Interview(GUIDED)
    for qid, value in [
        ("project_name", "x"),
        ("idea", "a small site"),
        ("project_kind", "web"),
        ("needs_backend", False),
        ("needs_auth", False),
        ("complexity", "simple"),
    ]:
        interview.answer(qid, value)
    assert "audience" not in interview.answers
    assert interview.is_complete() is True


def test_is_complete_true_for_expert_after_two_answers():
    interview = Interview(EXPERT)
    interview.answer("project_name", "x")
    interview.answer("idea", "y")
    assert interview.is_complete() is True


# --------------------------------------------------------------------------
# back()
# --------------------------------------------------------------------------

def test_back_at_the_start_returns_none():
    assert Interview(GUIDED).back() is None


def test_back_un_answers_the_previous_question():
    interview = Interview(GUIDED)
    interview.answer("project_name", "x")
    interview.answer("idea", "y")
    question = interview.back()
    assert question.id == "idea"
    assert "idea" not in interview.answers
    assert interview.next_question().id == "idea"


def test_back_twice_walks_backwards_in_answer_order():
    interview = Interview(GUIDED)
    interview.answer("project_name", "x")
    interview.answer("idea", "y")
    interview.back()
    assert interview.back().id == "project_name"
    assert interview.answers == {}
    assert interview.back() is None


def test_back_across_a_branch_boundary_closes_the_branch_again():
    interview = Interview(GUIDED)
    interview.answer("project_name", "runlog")
    interview.answer("idea", "log my runs")
    interview.answer("project_kind", "web")
    interview.answer("audience", "me")
    interview.answer("features", ["auth", "storage"])

    opened = ids_of(interview.applicable())
    assert "database" in opened            # storage features opened it
    assert "needs_auth" not in opened      # inferred from the auth feature
    assert interview.next_question().id == "database"
    interview.answer("database", "sqlite")

    assert interview.back().id == "database"
    assert interview.back().id == "features"

    closed = ids_of(interview.applicable())
    assert "database" not in closed
    assert "needs_auth" in closed
    assert "needs_auth" not in interview.answers
    assert "needs_backend" not in interview.answers
    assert "features" not in interview.answers


def test_back_over_project_kind_removes_the_inferred_backend_answer():
    interview = Interview(GUIDED)
    interview.answer("project_name", "api")
    interview.answer("project_kind", "backend")
    assert interview.answers["needs_backend"] is True
    assert interview.back().id == "project_kind"
    assert "needs_backend" not in interview.answers
    assert "needs_backend" in ids_of(interview.applicable())


def test_back_does_not_un_answer_prefilled_values():
    interview = Interview(GUIDED)
    interview.prefill({"project_name": "seeded", "idea": "seeded idea"})
    assert interview.back() is None
    assert interview.answers["project_name"] == "seeded"


def test_back_re_answering_produces_the_same_state_as_answering_once():
    walk = [("project_name", "x"), ("idea", "y"), ("project_kind", "mobile")]
    straight = Interview(GUIDED)
    for qid, value in walk:
        straight.answer(qid, value)

    detoured = Interview(GUIDED)
    for qid, value in walk:
        detoured.answer(qid, value)
    detoured.answer("audience", "me")
    detoured.back()
    assert detoured.answers == straight.answers
    assert ids_of(detoured.applicable()) == ids_of(straight.applicable())


# --------------------------------------------------------------------------
# prefill
# --------------------------------------------------------------------------

def test_prefill_skips_questions_that_are_already_answered():
    interview = Interview(GUIDED)
    interview.prefill({"project_name": "seeded", "project_kind": "mobile"})
    assert interview.next_question().id == "idea"


def test_prefill_ignores_unknown_ids():
    interview = Interview(GUIDED)
    interview.prefill({"not_a_question": "x", "project_name": "ok"})
    assert "not_a_question" not in interview.answers
    assert interview.answers["project_name"] == "ok"


def test_prefill_ignores_unusable_values_instead_of_raising():
    interview = Interview(GUIDED)
    interview.prefill({"project_kind": "django", "features": 5, "idea": "fine"})
    assert "project_kind" not in interview.answers
    assert "features" not in interview.answers
    assert interview.answers["idea"] == "fine"


def test_prefill_applies_inference_too():
    interview = Interview(GUIDED)
    interview.prefill({"features": ["auth"]})
    assert interview.answers["needs_auth"] is True


def test_constructor_answers_are_prefilled():
    interview = Interview(GUIDED, {"project_name": "seeded"})
    assert interview.answers["project_name"] == "seeded"


# --------------------------------------------------------------------------
# to_brief
# --------------------------------------------------------------------------

def test_to_brief_maps_every_question_id_to_its_field():
    interview = Interview(GUIDED)
    interview.prefill(
        {
            "project_name": "runlog",
            "idea": "log my runs",
            "project_kind": "fullstack",
            "audience": "friends",
            "features": ["auth", "storage"],
            "needs_backend": True,
            "needs_auth": True,
            "database": "postgres",
            "styling": "tailwind",
            "complexity": "ambitious",
            "deploy_target": "cloud",
            "notes": "offline first",
        }
    )
    brief = interview.to_brief()
    assert brief.name == "runlog"
    assert brief.idea == "log my runs"
    assert brief.project_kind == "fullstack"
    assert brief.audience == "friends"
    assert brief.features == ["auth", "storage"]
    assert brief.needs_backend is True
    assert brief.needs_auth is True
    assert brief.database == "postgres"
    assert brief.styling == "tailwind"
    assert brief.complexity == "ambitious"
    assert brief.deploy_target == "cloud"
    assert brief.notes == "offline first"


def test_to_brief_keeps_the_raw_answers():
    interview = Interview(EXPERT)
    interview.answer("project_name", "x")
    assert interview.to_brief().answers["project_name"] == "x"


def test_to_brief_of_an_untouched_interview_is_empty():
    assert Interview(GUIDED).to_brief().is_empty() is True


def test_to_brief_defaults_complexity_to_simple():
    interview = Interview(EXPERT)
    interview.answer("project_name", "x")
    assert interview.to_brief().complexity == "simple"


def test_to_brief_carries_the_auth_inference():
    interview = Interview(GUIDED)
    interview.answer("features", ["auth"])
    brief = interview.to_brief()
    assert brief.needs_auth is True
    assert brief.needs_backend is True


def test_to_brief_produces_a_usable_planner_prompt():
    interview = Interview(QUICK)
    interview.answer("project_name", "runlog")
    interview.answer("idea", "log my runs")
    interview.answer("project_kind", "mobile")
    interview.answer("complexity", "simple")
    prompt = interview.to_brief().to_prompt()
    assert "runlog" in prompt
    assert "phone" in prompt


def test_reset_clears_answers_and_history():
    interview = Interview(GUIDED)
    interview.answer("project_name", "x")
    interview.reset()
    assert interview.answers == {}
    assert interview.back() is None


def test_prefill_keeps_free_text_audience_and_features():
    """Recipes describe the audience and features in their own words."""
    interview = Interview(GUIDED)
    interview.prefill(
        {
            "audience": "recruiters and potential clients",
            "features": ["project gallery", "resume download"],
            "deploy_target": "vercel",
            "styling": "css",
        }
    )
    brief = interview.to_brief()
    assert brief.audience == "recruiters and potential clients"
    assert brief.features == ["project gallery", "resume download"]
    assert brief.deploy_target == "vercel"
    assert brief.styling == "css"


def test_prefill_still_rejects_invalid_closed_vocabulary_values():
    interview = Interview(GUIDED)
    interview.prefill({"project_kind": "django", "complexity": "epic", "database": "csv"})
    assert interview.answers == {}


def test_answer_stays_strict_even_though_prefill_is_lenient():
    with pytest.raises(ValueError):
        Interview(GUIDED).answer("audience", "recruiters and potential clients")
