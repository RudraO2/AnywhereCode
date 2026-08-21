"""Tests for anyplace.core.code_generator.

The interesting parts are the ones that touch the filesystem: where files are
written (path-traversal safety), the checkpoint/resume round trip, markdown
fence stripping, and failure cleanup.
"""

from __future__ import annotations

import json

import pytest

from anyplace.cli.error_handler import APIError, GenerationError
from anyplace.core import code_generator as cg_mod
from anyplace.core.code_generator import CodeGenerator, GenerationCheckpoint
from anyplace.core.plan_generator import FileInfo, ProjectPlan

try:
    from tests.helpers import ExplodingLLM, StubLLM
except ImportError:  # pragma: no cover - depends on rootdir layout
    from helpers import ExplodingLLM, StubLLM


@pytest.fixture
def project_dir(tmp_path):
    d = tmp_path / "generated" / "demo-project"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def generator(sample_plan, project_dir):
    return CodeGenerator(
        sample_plan,
        llm_provider=StubLLM(text="generated content"),
        project_dir=project_dir,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_init_uses_explicit_project_dir(sample_plan, project_dir):
    gen = CodeGenerator(sample_plan, llm_provider=StubLLM(), project_dir=project_dir)
    assert gen.project_dir == project_dir


def test_init_defaults_project_dir_to_projects_dir_plus_name(
    sample_plan, fake_projects_dir
):
    gen = CodeGenerator(sample_plan, llm_provider=StubLLM())
    assert gen.project_dir == fake_projects_dir / "demo-project"


def test_init_starts_with_no_generated_files_or_checkpoints(generator):
    assert generator.files_generated == []
    assert generator.checkpoints == []


# ---------------------------------------------------------------------------
# _write_file -- path traversal is a security boundary
# ---------------------------------------------------------------------------


def test_write_file_creates_nested_parent_directories(generator, project_dir):
    generator._write_file("src/components/Button.tsx", "export default 1;")
    written = project_dir / "src" / "components" / "Button.tsx"
    assert written.read_text() == "export default 1;"


def test_write_file_overwrites_existing_content(generator, project_dir):
    generator._write_file("a.txt", "first")
    generator._write_file("a.txt", "second")
    assert (project_dir / "a.txt").read_text() == "second"


def test_write_file_writes_empty_content_without_error(generator, project_dir):
    generator._write_file("empty.txt", "")
    assert (project_dir / "empty.txt").read_text() == ""


def test_write_file_raises_generation_error_when_path_is_a_directory(
    generator, project_dir
):
    (project_dir / "adir").mkdir()
    with pytest.raises(GenerationError) as excinfo:
        generator._write_file("adir", "content")
    assert "adir" in str(excinfo.value)


@pytest.mark.parametrize(
    "evil_path",
    [
        "../escaped.txt",
        "../../escaped.txt",
        "src/../../escaped.txt",
        "./../escaped.txt",
        "a/b/../../../escaped.txt",
    ],
)
def test_write_file_refuses_to_escape_project_dir_via_dotdot(
    generator, project_dir, evil_path
):
    with pytest.raises(GenerationError) as excinfo:
        generator._write_file(evil_path, "pwned")
    assert "outside the project" in str(excinfo.value)
    assert not (project_dir.parent / "escaped.txt").exists()


@pytest.mark.parametrize("evil_path", ["/tmp/absolute-escape.txt", "/etc/passwd"])
def test_write_file_refuses_absolute_paths(generator, evil_path):
    with pytest.raises(GenerationError) as excinfo:
        generator._write_file(evil_path, "pwned")
    assert "absolute path" in str(excinfo.value)


def test_write_file_refuses_a_path_that_resolves_to_the_project_root(generator):
    for path in ("", ".", "src/.."):
        with pytest.raises(GenerationError):
            generator._write_file(path, "pwned")


def test_write_file_allows_a_leading_dot_slash(generator, project_dir):
    generator._write_file("./a.txt", "ok")
    assert (project_dir / "a.txt").read_text() == "ok"


def test_write_file_allows_dotdot_that_stays_inside_the_project(generator, project_dir):
    generator._write_file("src/nested/../App.tsx", "ok")
    assert (project_dir / "src" / "App.tsx").read_text() == "ok"


def test_generate_all_aborts_when_the_plan_contains_an_escaping_path(
    project_dir, tmp_path
):
    evil = ProjectPlan(
        "evil",
        "t",
        "",
        [],
        [FileInfo("../../pwned.txt", "d", "source", [])],
        [],
        "",
        "",
        [],
    )
    gen = CodeGenerator(evil, llm_provider=StubLLM(text="x"), project_dir=project_dir)
    with pytest.raises(GenerationError):
        gen.generate_all()
    assert not (tmp_path / "pwned.txt").exists()


# ---------------------------------------------------------------------------
# _generate_file_content -- markdown fence stripping
# ---------------------------------------------------------------------------


def content_generator(sample_plan, project_dir, text):
    return CodeGenerator(
        sample_plan, llm_provider=StubLLM(text=text), project_dir=project_dir
    )


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("print('hi')", "print('hi')"),
        ("  print('hi')  \n", "print('hi')"),
        ("```python\nprint('hi')\n```", "print('hi')"),
        ("```\nprint('hi')\n```", "print('hi')"),
        ("Here you go:\n```py\nprint('hi')\n```\nEnjoy!", "print('hi')"),
        ("```json\n{\n  \"a\": 1\n}\n```", '{\n  "a": 1\n}'),
        ("```ts\nconst a = 1;\nconst b = 2;\n```", "const a = 1;\nconst b = 2;"),
    ],
    ids=[
        "plain",
        "plain_with_whitespace",
        "language_fence",
        "bare_fence",
        "fence_with_prose",
        "json_fence_preserves_indent",
        "multi_line_body",
    ],
)
def test_generate_file_content_strips_markdown_fences(
    sample_plan, project_dir, raw, expected
):
    gen = content_generator(sample_plan, project_dir, raw)
    assert gen._generate_file_content(sample_plan.files[0]) == expected


def test_generate_file_content_keeps_only_the_first_code_block(sample_plan, project_dir):
    raw = "```py\nfirst = 1\n```\nthen\n```py\nsecond = 2\n```"
    gen = content_generator(sample_plan, project_dir, raw)
    assert gen._generate_file_content(sample_plan.files[0]) == "first = 1"


def test_generate_file_content_leaves_empty_fence_untouched(sample_plan, project_dir):
    # No lines inside the fence -> nothing to substitute, so the raw text stays.
    gen = content_generator(sample_plan, project_dir, "```\n```")
    assert gen._generate_file_content(sample_plan.files[0]) == "```\n```"


def test_generate_file_content_prompt_names_the_target_file(generator, sample_plan):
    generator._generate_file_content(sample_plan.files[1])
    prompt = generator.llm_provider.text_calls[0]["prompt"]
    assert "src/App.tsx" in prompt
    assert "Root React component" in prompt


def test_generate_file_content_prompt_lists_dependencies(generator, sample_plan):
    generator._generate_file_content(sample_plan.files[2])
    prompt = generator.llm_provider.text_calls[0]["prompt"]
    assert "- src/App.tsx" in prompt
    assert "- package.json" in prompt


def test_generate_file_content_prompt_says_no_dependencies_when_empty(
    generator, sample_plan
):
    generator._generate_file_content(sample_plan.files[0])
    assert "No dependencies" in generator.llm_provider.text_calls[0]["prompt"]


def test_generate_file_content_prompt_mentions_already_generated_files(
    generator, sample_plan
):
    generator.files_generated.append("package.json")
    generator._generate_file_content(sample_plan.files[1])
    assert "Already generated:" in generator.llm_provider.text_calls[0]["prompt"]


def test_generate_file_content_system_prompt_carries_project_metadata(generator):
    system = generator._build_generation_system()
    assert "demo-project" in system
    assert "web-react-vite" in system
    assert "React" in system


def test_generate_file_content_propagates_api_error(sample_plan, project_dir):
    gen = CodeGenerator(
        sample_plan,
        llm_provider=ExplodingLLM(APIError("no key")),
        project_dir=project_dir,
    )
    with pytest.raises(APIError):
        gen._generate_file_content(sample_plan.files[0])


def test_generate_file_content_wraps_other_errors_as_generation_error(
    sample_plan, project_dir
):
    gen = CodeGenerator(
        sample_plan,
        llm_provider=ExplodingLLM(ValueError("boom")),
        project_dir=project_dir,
    )
    with pytest.raises(GenerationError) as excinfo:
        gen._generate_file_content(sample_plan.files[0])
    assert "boom" in str(excinfo.value)


# ---------------------------------------------------------------------------
# generate_all
# ---------------------------------------------------------------------------


def test_generate_all_writes_every_planned_file(generator, sample_plan, project_dir):
    assert generator.generate_all() is True
    for file_info in sample_plan.files:
        assert (project_dir / file_info.path).read_text() == "generated content"


def test_generate_all_records_every_file_it_generated(generator, sample_plan):
    generator.generate_all()
    assert generator.files_generated == [f.path for f in sample_plan.files]


def test_generate_all_creates_the_project_dir_when_missing(sample_plan, tmp_path):
    target = tmp_path / "not" / "yet" / "there"
    gen = CodeGenerator(sample_plan, llm_provider=StubLLM(text="x"), project_dir=target)
    gen.generate_all()
    assert target.is_dir()


def test_generate_all_reports_progress_for_each_file(generator, sample_plan):
    seen = []
    generator.generate_all(progress_callback=lambda p, i, t: seen.append((p, i, t)))

    total = len(sample_plan.files)
    assert [s[0] for s in seen] == [f.path for f in sample_plan.files]
    assert [s[1] for s in seen] == list(range(1, total + 1))
    assert all(s[2] == total for s in seen)


def test_generate_all_marks_final_checkpoint_successful(generator):
    generator.generate_all()
    assert generator.checkpoints[-1].success is True
    assert generator.can_resume() is False


def test_generate_all_raises_generation_error_naming_the_failed_file(
    sample_plan, project_dir
):
    gen = CodeGenerator(
        sample_plan,
        llm_provider=ExplodingLLM(APIError("provider down")),
        project_dir=project_dir,
    )
    with pytest.raises(GenerationError) as excinfo:
        gen.generate_all()
    assert "package.json" in str(excinfo.value)
    assert "provider down" in str(excinfo.value)


def test_generate_all_leaves_a_resumable_checkpoint_after_failure(
    sample_plan, project_dir
):
    calls = {"n": 0}

    def flaky(prompt, **kwargs):
        calls["n"] += 1
        if calls["n"] > 2:
            raise APIError("provider down")
        return "ok"

    gen = CodeGenerator(
        sample_plan, llm_provider=StubLLM(text=flaky), project_dir=project_dir
    )
    with pytest.raises(GenerationError):
        gen.generate_all()

    assert gen.can_resume() is True
    info = gen.get_resume_info()
    assert info["files_done"] == 2
    assert info["total_files"] == len(sample_plan.files)
    assert info["next_file_index"] == 3


def test_generate_all_succeeds_with_an_empty_plan(project_dir):
    empty = ProjectPlan("empty", "t", "", [], [], [], "", "", [])
    gen = CodeGenerator(empty, llm_provider=StubLLM(), project_dir=project_dir)
    assert gen.generate_all() is True
    assert gen.files_generated == []


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


def test_save_checkpoint_appends_to_the_in_memory_list(generator):
    generator._save_checkpoint(1, 4, success=False)
    generator._save_checkpoint(2, 4, success=False)
    assert len(generator.checkpoints) == 2
    assert isinstance(generator.checkpoints[0], GenerationCheckpoint)
    assert generator.checkpoints[1].current_index == 2


def test_save_checkpoint_writes_checkpoints_json_under_dot_logs(generator, project_dir):
    generator.files_generated.append("package.json")
    generator._save_checkpoint(1, 4, success=False)

    data = json.loads((project_dir / ".logs" / "checkpoints.json").read_text())
    assert len(data) == 1
    assert data[0]["files_generated"] == ["package.json"]
    assert data[0]["current_index"] == 1
    assert data[0]["total_files"] == 4
    assert data[0]["success"] is False
    assert data[0]["timestamp"]


def test_save_checkpoint_round_trips_the_full_history(generator, project_dir):
    for index, path in enumerate(["a", "b", "c"], start=1):
        generator.files_generated.append(path)
        generator._save_checkpoint(index, 3, success=index == 3)

    data = json.loads((project_dir / ".logs" / "checkpoints.json").read_text())
    assert [d["current_index"] for d in data] == [1, 2, 3]
    assert [d["files_generated"] for d in data] == [["a"], ["a", "b"], ["a", "b", "c"]]
    assert [d["success"] for d in data] == [False, False, True]


def test_save_checkpoint_snapshots_files_generated_rather_than_aliasing(generator):
    generator.files_generated.append("a")
    generator._save_checkpoint(1, 2, success=False)
    generator.files_generated.append("b")
    assert generator.checkpoints[0].files_generated == ["a"]


def test_save_checkpoint_does_not_raise_when_logs_cannot_be_written(
    generator, project_dir, monkeypatch
):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cg_mod.json, "dump", boom)
    generator._save_checkpoint(1, 2, success=False)  # must not raise
    assert len(generator.checkpoints) == 1


# ---------------------------------------------------------------------------
# can_resume / get_resume_info
# ---------------------------------------------------------------------------


def test_can_resume_is_false_without_any_checkpoint(generator):
    assert generator.can_resume() is False
    assert generator.get_resume_info() == {}


def test_can_resume_is_false_when_nothing_was_generated_yet(generator):
    generator._save_checkpoint(1, 3, success=False)
    assert generator.can_resume() is False


def test_can_resume_is_true_after_partial_failure(generator):
    generator.files_generated.append("package.json")
    generator._save_checkpoint(1, 3, success=False)
    assert generator.can_resume() is True


def test_can_resume_is_false_after_a_successful_run(generator):
    generator.files_generated.append("package.json")
    generator._save_checkpoint(3, 3, success=True)
    assert generator.can_resume() is False


def test_get_resume_info_reports_progress_and_timestamp(generator):
    generator.files_generated.extend(["a", "b"])
    generator._save_checkpoint(2, 5, success=False)

    info = generator.get_resume_info()
    assert info["files_done"] == 2
    assert info["total_files"] == 5
    assert info["next_file_index"] == 2
    assert info["timestamp"] == generator.checkpoints[-1].timestamp


# ---------------------------------------------------------------------------
# cleanup_on_failure
# ---------------------------------------------------------------------------


def test_cleanup_on_failure_removes_the_project_dir(generator, project_dir):
    generator._write_file("a.txt", "x")
    generator.cleanup_on_failure()
    assert not project_dir.exists()


def test_cleanup_on_failure_is_a_noop_when_dir_is_absent(sample_plan, tmp_path):
    missing = tmp_path / "never-created"
    gen = CodeGenerator(sample_plan, llm_provider=StubLLM(), project_dir=missing)
    gen.cleanup_on_failure()  # must not raise
    assert not missing.exists()


def test_cleanup_on_failure_swallows_removal_errors(generator, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: (_ for _ in ()).throw(OSError("busy")))
    generator.cleanup_on_failure()  # must not raise
