"""Tests for anyplace.core.plan_generator.

Covers response parsing, plan validation and the dependency-ordering pass.
No network: every LLM here is a stub or the project's own MockLLMProvider.
"""

from __future__ import annotations

import json

import pytest

from anyplace.cli.error_handler import GenerationError
from anyplace.core.plan_generator import (
    PLAN_RESPONSE_SCHEMA,
    FileInfo,
    PlanGenerator,
    ProjectPlan,
)

try:
    from tests.helpers import ExplodingLLM, StubLLM
except ImportError:  # pragma: no cover - depends on rootdir layout
    from helpers import ExplodingLLM, StubLLM


COMPLETE_PLAN_JSON = {
    "project_name": "demo",
    "template": "web-react-vite",
    "description": "A demo app",
    "tech_stack": ["React", "Vite"],
    "files": [
        {
            "path": "package.json",
            "description": "deps",
            "file_type": "config",
            "dependencies": [],
        },
        {
            "path": "src/App.tsx",
            "description": "root component",
            "file_type": "source",
            "dependencies": ["package.json"],
        },
    ],
    "key_features": ["fast"],
    "estimated_time": "10 minutes",
    "architecture_notes": "SPA",
    "next_steps": ["npm install"],
}


@pytest.fixture
def generator():
    """A PlanGenerator wired to a stub LLM that returns a complete plan."""
    return PlanGenerator(llm_provider=StubLLM(json_value=dict(COMPLETE_PLAN_JSON)))


def file_info(path, deps=()):
    return FileInfo(
        path=path, description="d", file_type="source", dependencies=list(deps)
    )


# ---------------------------------------------------------------------------
# ProjectPlan / FileInfo dataclasses
# ---------------------------------------------------------------------------


def test_project_plan_to_dict_round_trips_nested_file_info(sample_plan):
    as_dict = sample_plan.to_dict()
    assert as_dict["project_name"] == "demo-project"
    assert isinstance(as_dict["files"], list)
    assert as_dict["files"][0]["path"] == "package.json"
    assert as_dict["files"][0]["dependencies"] == []


def test_project_plan_to_json_is_valid_json(sample_plan):
    reparsed = json.loads(sample_plan.to_json())
    assert reparsed["template"] == "web-react-vite"
    assert len(reparsed["files"]) == len(sample_plan.files)


def test_plan_response_schema_requires_every_top_level_field():
    assert set(PLAN_RESPONSE_SCHEMA["required"]) == set(
        PLAN_RESPONSE_SCHEMA["properties"].keys()
    )
    assert PLAN_RESPONSE_SCHEMA["type"] == "OBJECT"


# ---------------------------------------------------------------------------
# _parse_plan_response
# ---------------------------------------------------------------------------


def test_parse_plan_response_maps_every_field_from_complete_output(generator):
    plan = generator._parse_plan_response(COMPLETE_PLAN_JSON, "web-react-vite", "fallback")

    assert plan.project_name == "demo"
    assert plan.template == "web-react-vite"
    assert plan.description == "A demo app"
    assert plan.tech_stack == ["React", "Vite"]
    assert plan.key_features == ["fast"]
    assert plan.estimated_time == "10 minutes"
    assert plan.architecture_notes == "SPA"
    assert plan.next_steps == ["npm install"]
    assert [f.path for f in plan.files] == ["package.json", "src/App.tsx"]
    assert plan.files[1].dependencies == ["package.json"]


def test_parse_plan_response_template_always_comes_from_the_caller(generator):
    payload = dict(COMPLETE_PLAN_JSON, template="the-llm-made-this-up")
    plan = generator._parse_plan_response(payload, "web-react-vite", "fallback")
    assert plan.template == "web-react-vite"


def test_parse_plan_response_falls_back_to_supplied_project_name(generator):
    payload = {k: v for k, v in COMPLETE_PLAN_JSON.items() if k != "project_name"}
    plan = generator._parse_plan_response(payload, "tpl", "fallback-name")
    assert plan.project_name == "fallback-name"


def test_parse_plan_response_fills_defaults_for_partial_output(generator):
    payload = {"project_name": "partial", "files": []}
    plan = generator._parse_plan_response(payload, "tpl", "fallback")

    assert plan.project_name == "partial"
    assert plan.files == []
    assert plan.tech_stack == []
    assert plan.key_features == []
    assert plan.next_steps == []
    assert plan.description == ""
    assert plan.architecture_notes == ""
    assert plan.estimated_time == "Unknown"


def test_parse_plan_response_defaults_missing_file_fields(generator):
    plan = generator._parse_plan_response({"files": [{}]}, "tpl", "p")
    only = plan.files[0]
    assert only.path == ""
    assert only.description == ""
    assert only.file_type == "other"
    assert only.dependencies == []


@pytest.mark.parametrize("payload", [{}, {"files": None}, {"project_name": "p"}])
def test_parse_plan_response_rejects_a_payload_with_no_files_key(generator, payload):
    with pytest.raises(GenerationError) as excinfo:
        generator._parse_plan_response(payload, "tpl", "p")
    assert "no 'files'" in str(excinfo.value)


def test_parse_plan_response_accepts_an_explicitly_empty_files_list(generator):
    assert generator._parse_plan_response({"files": []}, "tpl", "p").files == []


@pytest.mark.parametrize(
    "files_value, needle",
    [
        ("not-a-list", "should be a list"),
        ({"path": "a"}, "should be a list"),
        (42, "should be a list"),
    ],
    ids=["string", "dict", "number"],
)
def test_parse_plan_response_rejects_a_files_value_that_is_not_a_list(
    generator, files_value, needle
):
    with pytest.raises(GenerationError) as excinfo:
        generator._parse_plan_response({"files": files_value}, "tpl", "p")
    assert needle in str(excinfo.value)


@pytest.mark.parametrize("files_value", [[1, 2, 3], ["a", "b"], [None], [{}, "x"]])
def test_parse_plan_response_rejects_non_dict_file_entries(generator, files_value):
    with pytest.raises(GenerationError) as excinfo:
        generator._parse_plan_response({"files": files_value}, "tpl", "p")
    assert "should be an object" in str(excinfo.value)


def test_parse_plan_response_names_the_offending_file_index(generator):
    payload = {"files": [{"path": "ok.txt"}, "junk"]}
    with pytest.raises(GenerationError) as excinfo:
        generator._parse_plan_response(payload, "tpl", "p")
    assert "files[1]" in str(excinfo.value)


@pytest.mark.parametrize("payload", [[], "a string", 42, None, [{"a": 1}]])
def test_parse_plan_response_rejects_a_payload_that_is_not_an_object(generator, payload):
    with pytest.raises(GenerationError) as excinfo:
        generator._parse_plan_response(payload, "tpl", "p")
    assert "expected an object" in str(excinfo.value)


def test_parse_plan_response_wraps_a_scalar_dependency_in_a_list(generator):
    payload = {"files": [{"path": "a.txt", "dependencies": "b.txt"}]}
    assert generator._parse_plan_response(payload, "tpl", "p").files[0].dependencies == ["b.txt"]


def test_parse_plan_response_treats_a_null_dependency_list_as_empty(generator):
    payload = {"files": [{"path": "a.txt", "dependencies": None}]}
    assert generator._parse_plan_response(payload, "tpl", "p").files[0].dependencies == []


def test_parse_plan_response_stringifies_non_string_file_fields(generator):
    payload = {"files": [{"path": 42, "description": None, "dependencies": [7]}]}
    only = generator._parse_plan_response(payload, "tpl", "p").files[0]
    assert only.path == "42"
    assert only.description == ""
    assert only.dependencies == ["7"]


@pytest.mark.parametrize(
    "field", ["tech_stack", "key_features", "next_steps"]
)
def test_parse_plan_response_coerces_a_bare_string_list_field(generator, field):
    plan = generator._parse_plan_response({field: "just one", "files": []}, "tpl", "p")
    assert getattr(plan, field) == ["just one"]


@pytest.mark.parametrize("field", ["tech_stack", "key_features", "next_steps"])
def test_parse_plan_response_treats_a_null_list_field_as_empty(generator, field):
    plan = generator._parse_plan_response({field: None, "files": []}, "tpl", "p")
    assert getattr(plan, field) == []


def test_parse_plan_response_drops_nulls_from_list_fields(generator):
    payload = {"tech_stack": ["React", None, "Vite"], "files": []}
    plan = generator._parse_plan_response(payload, "t", "p")
    assert plan.tech_stack == ["React", "Vite"]


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------


def test_validate_plan_accepts_a_well_formed_plan(generator, sample_plan):
    assert generator.validate_plan(sample_plan) is True


def test_validate_plan_accepts_files_with_no_dependencies(generator):
    plan = ProjectPlan("p", "t", "", [], [file_info("a.txt")], [], "", "", [])
    assert generator.validate_plan(plan) is True


@pytest.mark.parametrize(
    "field, value",
    [("project_name", ""), ("template", "")],
    ids=["missing_project_name", "missing_template"],
)
def test_validate_plan_rejects_missing_required_field(generator, sample_plan, field, value):
    setattr(sample_plan, field, value)
    assert generator.validate_plan(sample_plan) is False


def test_validate_plan_rejects_plan_with_no_files(generator, sample_plan):
    sample_plan.files = []
    assert generator.validate_plan(sample_plan) is False


def test_validate_plan_rejects_unresolved_file_dependency(generator, sample_plan):
    sample_plan.files[0].dependencies = ["does/not/exist.ts"]
    assert generator.validate_plan(sample_plan) is False


def test_validate_plan_accepts_self_referential_dependency(generator):
    # Documents current behaviour: validate_plan only checks that the path is
    # known, so a file listing itself passes validation (the cycle is caught
    # later, by topological_sort_files).
    plan = ProjectPlan("p", "t", "", [], [file_info("a.txt", ["a.txt"])], [], "", "", [])
    assert generator.validate_plan(plan) is True


# ---------------------------------------------------------------------------
# topological_sort_files
# ---------------------------------------------------------------------------


def test_topological_sort_files_places_dependencies_before_dependents(generator, sample_plan):
    ordered = [f.path for f in generator.topological_sort_files(sample_plan.files)]

    assert ordered.index("package.json") < ordered.index("src/App.tsx")
    assert ordered.index("src/App.tsx") < ordered.index("src/main.tsx")
    assert set(ordered) == {f.path for f in sample_plan.files}


def test_topological_sort_files_preserves_every_file(generator, sample_plan):
    assert len(generator.topological_sort_files(sample_plan.files)) == len(sample_plan.files)


def test_topological_sort_files_returns_empty_list_for_no_files(generator):
    assert generator.topological_sort_files([]) == []


def test_topological_sort_files_keeps_input_order_when_no_dependencies(generator):
    files = [file_info("c"), file_info("a"), file_info("b")]
    assert [f.path for f in generator.topological_sort_files(files)] == ["c", "a", "b"]


def test_topological_sort_files_ignores_dependencies_outside_the_plan(generator):
    files = [file_info("a.txt", ["node_modules/react/index.js"])]
    assert [f.path for f in generator.topological_sort_files(files)] == ["a.txt"]


def test_topological_sort_files_handles_a_long_chain(generator):
    names = ["f%02d" % i for i in range(30)]
    files = [file_info(names[0])]
    files += [file_info(names[i], [names[i - 1]]) for i in range(1, 30)]
    assert [f.path for f in generator.topological_sort_files(files)] == names


def test_topological_sort_files_raises_on_two_node_cycle(generator):
    files = [file_info("a", ["b"]), file_info("b", ["a"])]
    with pytest.raises(GenerationError) as excinfo:
        generator.topological_sort_files(files)
    assert "circular" in str(excinfo.value).lower()


def test_topological_sort_files_raises_on_self_dependency(generator):
    with pytest.raises(GenerationError):
        generator.topological_sort_files([file_info("a", ["a"])])


def test_topological_sort_files_terminates_on_a_large_cycle(generator):
    # Regression guard: Kahn's algorithm must exit, not spin, on a big cycle.
    names = ["n%02d" % i for i in range(50)]
    files = [file_info(names[i], [names[i - 1]]) for i in range(50)]
    with pytest.raises(GenerationError):
        generator.topological_sort_files(files)


def test_topological_sort_files_sorts_a_diamond_dependency(generator):
    files = [
        file_info("d", ["b", "c"]),
        file_info("b", ["a"]),
        file_info("c", ["a"]),
        file_info("a"),
    ]
    ordered = [f.path for f in generator.topological_sort_files(files)]
    assert ordered[0] == "a"
    assert ordered[-1] == "d"
    assert ordered.index("b") < ordered.index("d")
    assert ordered.index("c") < ordered.index("d")


# ---------------------------------------------------------------------------
# generate_plan (end to end, stubbed LLM)
# ---------------------------------------------------------------------------


def test_generate_plan_returns_validated_plan_from_llm_output(generator):
    plan = generator.generate_plan("web-react-vite", "demo", "a demo app")

    assert isinstance(plan, ProjectPlan)
    assert plan.project_name == "demo"
    assert plan.template == "web-react-vite"
    assert len(plan.files) == 2


def test_generate_plan_passes_response_schema_to_the_provider(generator):
    generator.generate_plan("web-react-vite", "demo")
    assert generator.llm_provider.json_calls[0]["response_schema"] is PLAN_RESPONSE_SCHEMA


def test_generate_plan_includes_project_details_in_the_prompt(generator):
    generator.generate_plan("web-react-vite", "my-app", "a todo list")
    prompt = generator.llm_provider.json_calls[0]["prompt"]
    assert "my-app" in prompt
    assert "a todo list" in prompt


def test_generate_plan_says_no_description_when_none_supplied(generator):
    generator.generate_plan("web-react-vite", "my-app")
    assert "No additional description" in generator.llm_provider.json_calls[0]["prompt"]


def test_generate_plan_raises_when_template_is_unknown(generator):
    with pytest.raises(GenerationError) as excinfo:
        generator.generate_plan("no-such-template", "demo")
    assert "no-such-template" in str(excinfo.value)


def test_generate_plan_raises_when_llm_returns_a_plan_with_no_files():
    gen = PlanGenerator(llm_provider=StubLLM(json_value={"project_name": "x"}))
    with pytest.raises(GenerationError) as excinfo:
        gen.generate_plan("web-react-vite", "demo")
    assert "invalid" in str(excinfo.value).lower()


def test_generate_plan_raises_when_dependencies_do_not_resolve():
    payload = dict(
        COMPLETE_PLAN_JSON,
        files=[
            {
                "path": "src/App.tsx",
                "description": "d",
                "file_type": "source",
                "dependencies": ["src/ghost.tsx"],
            }
        ],
    )
    gen = PlanGenerator(llm_provider=StubLLM(json_value=payload))
    with pytest.raises(GenerationError):
        gen.generate_plan("web-react-vite", "demo")


def test_generate_plan_wraps_llm_failures_as_generation_error():
    gen = PlanGenerator(llm_provider=ExplodingLLM(RuntimeError("provider exploded")))
    with pytest.raises(GenerationError) as excinfo:
        gen.generate_plan("web-react-vite", "demo")
    assert "provider exploded" in str(excinfo.value)


def test_generate_plan_never_leaks_raw_api_error():
    from anyplace.cli.error_handler import APIError

    gen = PlanGenerator(llm_provider=ExplodingLLM(APIError("429 rate limited")))
    with pytest.raises(GenerationError) as excinfo:
        gen.generate_plan("web-react-vite", "demo")
    assert "429 rate limited" in str(excinfo.value)


def test_generate_plan_works_with_the_bundled_mock_provider(mock_llm):
    plan = PlanGenerator(llm_provider=mock_llm).generate_plan("web-react-vite", "demo")
    assert plan.files
    assert plan.template == "web-react-vite"


def test_mock_llm_plan_payload_parses_and_validates(mock_llm):
    # The mock's canned plan is still a useful fixture even though generate_plan
    # cannot call it directly (see the xfail above).
    gen = PlanGenerator(llm_provider=mock_llm)
    payload = mock_llm.generate_json("generate a plan")
    plan = gen._parse_plan_response(payload, "web-react-vite", "demo")
    assert gen.validate_plan(plan) is True
    assert len(gen.topological_sort_files(plan.files)) == len(plan.files)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_build_system_prompt_demands_raw_json(generator):
    system = generator._build_system_prompt()
    assert "ONLY valid JSON" in system
    assert "No markdown code fences" in system


def test_build_template_context_tolerates_a_sparse_template_info(generator):
    context = generator._build_template_context({}, "p", "")
    assert context["project_name"] == "p"
    assert context["tech_stack"] == []
    assert context["files_to_generate"] == []
    assert context["project_description"] == "No additional description"
