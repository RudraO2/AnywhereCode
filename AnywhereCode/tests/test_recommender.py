"""Tests for anyplace.core.recommender.

The fixtures below are deliberately *local* copies of the template shape, so
enriching the real templates/*/structure.json files cannot break these tests.
"""

import pytest

from anyplace.core.brief import ProjectBrief
from anyplace.core.recommender import Recommendation, best_match, explain, recommend

WEB = {
    "name": "web-react-vite",
    "type": "web",
    "description": "Single page website with React and Vite",
    "tech_stack": ["React", "Vite", "TypeScript"],
    "files_to_generate": ["package.json", "index.html", "src/main.tsx", "src/App.tsx"],
    "key_features": ["Instant dev server", "Dark mode ready"],
}
MOBILE = {
    "name": "mobile-expo-rn",
    "type": "mobile",
    "description": "Cross-platform mobile app for iOS and Android, works offline",
    "tech_stack": ["React Native", "Expo", "TypeScript"],
    "files_to_generate": ["app.json", "package.json", "app/index.tsx"],
    "key_features": ["One codebase for iOS and Android", "Push notifications"],
}
BACKEND_PY = {
    "name": "backend-python-fastapi",
    "type": "backend",
    "description": "Python API service with automatic docs",
    "tech_stack": ["Python", "FastAPI", "SQLAlchemy", "SQLite"],
    "files_to_generate": ["main.py", "models.py", "db.py", "requirements.txt"],
    "key_features": ["Typed endpoints", "JWT auth ready"],
}
BACKEND_JS = {
    "name": "backend-nodejs",
    "type": "backend",
    "description": "Node API service built on Express",
    "tech_stack": ["Node.js", "Express", "TypeScript"],
    "files_to_generate": ["index.ts", "routes.ts", "package.json", "tsconfig.json"],
    "key_features": ["Familiar middleware", "JWT auth ready"],
}
FULLSTACK = {
    "name": "fullstack-nextjs",
    "type": "fullstack",
    "description": "Full-stack app with Next.js, accounts and PostgreSQL",
    "tech_stack": ["Next.js", "TypeScript", "PostgreSQL", "Prisma"],
    "files_to_generate": [
        "package.json", "app/page.tsx", "app/api/health/route.ts", "lib/db.ts",
        "lib/auth.ts", "prisma/schema.prisma", "app/layout.tsx", "next.config.ts",
        ".env.example", "components/Button.tsx", "app/globals.css", "tsconfig.json",
    ],
    "key_features": ["App router", "Prisma ORM", "Ready for NextAuth"],
}
CLI = {
    "name": "cli-python-click",
    "type": "cli",
    "description": "A terminal tool built with Click",
    "tech_stack": ["Python", "Click"],
    "files_to_generate": ["cli.py", "setup.py"],
    "key_features": ["Runs anywhere Python runs"],
}

TEMPLATES = [WEB, MOBILE, BACKEND_PY, BACKEND_JS, FULLSTACK, CLI]


def names(recs):
    return [r.template for r in recs]


# --------------------------------------------------------------------------
# Steering by project kind
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kind,expected",
    [
        ("web", "web-react-vite"),
        ("mobile", "mobile-expo-rn"),
        ("fullstack", "fullstack-nextjs"),
        ("cli", "cli-python-click"),
    ],
)
def test_project_kind_steers_to_the_matching_template_family(kind, expected):
    top = best_match(ProjectBrief(project_kind=kind), TEMPLATES)
    assert top.template == expected


def test_backend_project_kind_steers_to_a_backend_template():
    top = best_match(ProjectBrief(project_kind="backend"), TEMPLATES)
    assert top.template in ("backend-python-fastapi", "backend-nodejs")


def test_every_template_is_scored_and_ranked():
    recs = recommend(ProjectBrief(project_kind="web"), TEMPLATES)
    assert len(recs) == len(TEMPLATES)
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_scores_are_normalised_between_zero_and_one():
    for rec in recommend(ProjectBrief(project_kind="mobile"), TEMPLATES):
        assert 0.0 <= rec.score <= 1.0


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_recommendations_are_deterministic_across_runs():
    brief = ProjectBrief(
        project_kind="fullstack", idea="a shop with logins", features=["auth"]
    )
    first = [(r.template, r.score, tuple(r.reasons)) for r in recommend(brief, TEMPLATES)]
    second = [(r.template, r.score, tuple(r.reasons)) for r in recommend(brief, TEMPLATES)]
    assert first == second


def test_ties_are_broken_by_template_name():
    twin_a = {"name": "zeta", "type": "web", "description": "same", "tech_stack": []}
    twin_b = {"name": "alpha", "type": "web", "description": "same", "tech_stack": []}
    recs = recommend(ProjectBrief(project_kind="web"), [twin_a, twin_b])
    assert recs[0].score == recs[1].score
    assert names(recs) == ["alpha", "zeta"]


def test_input_order_does_not_change_the_ranking():
    brief = ProjectBrief(project_kind="backend", idea="python api")
    forwards = names(recommend(brief, TEMPLATES))
    backwards = names(recommend(brief, list(reversed(TEMPLATES))))
    assert forwards == backwards


# --------------------------------------------------------------------------
# Robustness
# --------------------------------------------------------------------------

def test_empty_template_list_returns_no_recommendations():
    assert recommend(ProjectBrief(project_kind="web"), []) == []
    assert best_match(ProjectBrief(project_kind="web"), []) is None


def test_templates_missing_keys_do_not_raise():
    junk = [
        {"name": "bare"},
        {"name": "weird", "type": 123, "tech_stack": "not a list", "keywords": None},
        {"name": "nested", "description": {"a": "b"}, "files_to_generate": "nope"},
    ]
    recs = recommend(ProjectBrief(project_kind="web"), junk)
    assert names(recs) == sorted(names(recs))
    assert len(recs) == 3
    assert all(r.reasons for r in recs)


def test_templates_without_a_name_are_skipped():
    recs = recommend(ProjectBrief(), [{}, {"type": "web"}, {"name": "keeper"}])
    assert names(recs) == ["keeper"]


def test_non_dict_template_entries_are_skipped():
    recs = recommend(ProjectBrief(project_kind="web"), [None, 42, "nope", WEB])
    assert names(recs) == ["web-react-vite"]


def test_empty_brief_does_not_crash_and_is_low_confidence():
    top = best_match(ProjectBrief(), TEMPLATES)
    assert top is not None
    assert top.confidence == "low"
    assert top.reasons


def test_none_brief_is_treated_as_an_empty_brief():
    assert best_match(None, TEMPLATES) is not None


def test_brief_dict_is_accepted_as_well_as_a_brief_object():
    top = best_match({"project_kind": "mobile"}, TEMPLATES)
    assert top.template == "mobile-expo-rn"


# --------------------------------------------------------------------------
# Explanations
# --------------------------------------------------------------------------

def test_top_pick_always_has_reasons():
    for kind in ("web", "mobile", "backend", "fullstack", "cli", "unsure", ""):
        top = best_match(ProjectBrief(project_kind=kind), TEMPLATES)
        assert top.reasons, kind
        assert all(reason.strip() for reason in top.reasons)


def test_reasons_are_written_in_plain_words():
    top = best_match(ProjectBrief(project_kind="mobile"), TEMPLATES)
    joined = " ".join(top.reasons)
    assert "You said you're building a phone app." in joined
    assert "Expo lets you run it on iOS and Android from one codebase." in joined


def test_reasons_mention_matched_features():
    brief = ProjectBrief(project_kind="fullstack", features=["auth"], needs_auth=True)
    top = best_match(brief, TEMPLATES)
    assert any("accounts & login" in reason for reason in top.reasons)


def test_reasons_are_deduplicated_and_capped():
    brief = ProjectBrief(
        project_kind="fullstack",
        idea="next.js postgres prisma typescript accounts",
        features=["auth", "storage", "admin"],
        database="postgres",
        complexity="ambitious",
    )
    top = best_match(brief, TEMPLATES)
    assert len(top.reasons) == len(set(top.reasons))
    assert len(top.reasons) <= 5


def test_nextjs_carries_the_termux_caveat():
    rec = [r for r in recommend(ProjectBrief(project_kind="fullstack"), TEMPLATES)
           if r.template == "fullstack-nextjs"][0]
    assert any("Termux" in caveat for caveat in rec.caveats)


def test_client_only_template_warns_when_a_server_is_needed():
    brief = ProjectBrief(project_kind="web", needs_backend=True)
    rec = [r for r in recommend(brief, TEMPLATES) if r.template == "web-react-vite"][0]
    assert any("No server side" in caveat for caveat in rec.caveats)


def test_database_mismatch_becomes_a_caveat_not_a_crash():
    brief = ProjectBrief(project_kind="web", database="mongo")
    rec = [r for r in recommend(brief, TEMPLATES) if r.template == "web-react-vite"][0]
    assert any("mongo" in caveat for caveat in rec.caveats)


def test_explain_renders_reasons_and_caveats():
    text = explain(best_match(ProjectBrief(project_kind="mobile"), TEMPLATES))
    assert "mobile-expo-rn" in text
    assert "confidence" in text
    assert "- " in text


def test_explain_handles_no_recommendation():
    assert explain(None) == "No template matched."


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------

def test_idea_keywords_shift_the_ranking_between_similar_templates():
    pair = [BACKEND_PY, BACKEND_JS]
    python_brief = ProjectBrief(
        project_kind="backend", idea="a python service with fastapi", complexity="standard"
    )
    node_brief = ProjectBrief(
        project_kind="backend", idea="an express service on node", complexity="standard"
    )
    assert best_match(python_brief, pair).template == "backend-python-fastapi"
    assert best_match(node_brief, pair).template == "backend-nodejs"


def test_idea_keyword_reason_quotes_the_matched_word():
    brief = ProjectBrief(project_kind="backend", idea="a fastapi service")
    top = best_match(brief, [BACKEND_PY, BACKEND_JS])
    assert any("fastapi" in reason for reason in top.reasons)


def test_database_choice_promotes_the_template_that_ships_it():
    brief = ProjectBrief(project_kind="fullstack", database="postgres", needs_backend=True)
    top = best_match(brief, TEMPLATES)
    assert top.template == "fullstack-nextjs"
    assert any("postgres" in reason for reason in top.reasons)


def test_needs_backend_penalises_client_only_templates():
    with_server = ProjectBrief(project_kind="web", needs_backend=True)
    without = ProjectBrief(project_kind="web", needs_backend=False)
    scored_with = {r.template: r.score for r in recommend(with_server, TEMPLATES)}
    scored_without = {r.template: r.score for r in recommend(without, TEMPLATES)}
    assert scored_with["web-react-vite"] < scored_without["web-react-vite"]
    assert scored_with["fullstack-nextjs"] > scored_without["fullstack-nextjs"]


def test_minimal_complexity_prefers_the_smaller_scaffold():
    simple = ProjectBrief(project_kind="web", complexity="simple")
    ambitious = ProjectBrief(project_kind="web", complexity="ambitious")
    simple_scores = {r.template: r.score for r in recommend(simple, TEMPLATES)}
    ambitious_scores = {r.template: r.score for r in recommend(ambitious, TEMPLATES)}
    assert simple_scores["fullstack-nextjs"] < ambitious_scores["fullstack-nextjs"]


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------

def test_confidence_is_high_for_a_clear_unambiguous_brief():
    brief = ProjectBrief(
        name="runlog",
        idea="a phone app to log my runs offline",
        project_kind="mobile",
        features=["offline", "notifications"],
        complexity="simple",
    )
    assert best_match(brief, TEMPLATES).confidence == "high"


def test_confidence_is_low_when_the_field_is_tightly_bunched():
    rec = Recommendation(template="x", score=0.9, reasons=["r"], caveats=[])
    rec.margin = 0.001
    assert rec.confidence == "medium"
    rec.score = 0.3
    assert rec.confidence == "low"


def test_confidence_is_high_only_with_score_and_margin():
    rec = Recommendation(template="x", score=0.7, reasons=["r"])
    rec.margin = 0.2
    assert rec.confidence == "high"
    rec.margin = 0.02
    assert rec.confidence == "medium"


def test_margin_is_the_gap_to_the_runner_up():
    recs = recommend(ProjectBrief(project_kind="mobile"), TEMPLATES)
    assert recs[0].margin == pytest.approx(recs[0].score - recs[1].score, abs=1e-6)
    assert recs[-1].margin == 0.0


def test_single_template_is_uncontested():
    recs = recommend(ProjectBrief(project_kind="web"), [WEB])
    assert recs[0].margin == recs[0].score


def test_recommendation_to_dict_is_serialisable():
    data = best_match(ProjectBrief(project_kind="web"), TEMPLATES).to_dict()
    assert data["template"] == "web-react-vite"
    assert data["confidence"] in ("high", "medium", "low")
    assert isinstance(data["reasons"], list)


def test_free_text_features_match_on_their_own_words():
    """Recipe features are phrases, not option ids -- they must still score."""
    brief = ProjectBrief(project_kind="mobile", features=["push notifications"])
    rec = [r for r in recommend(brief, TEMPLATES) if r.template == "mobile-expo-rn"][0]
    assert any("push notifications" in reason for reason in rec.reasons)


def test_free_text_features_that_match_nothing_are_harmless():
    brief = ProjectBrief(project_kind="web", features=["a wholly unrelated phrase"])
    top = best_match(brief, TEMPLATES)
    assert top.template == "web-react-vite"
    assert 0.0 <= top.score <= 1.0
