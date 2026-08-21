"""Tests for anyplace.core.build_runner.

Project-type detection is a plain function of which marker files exist, so it
is exhaustively parametrized here, including the cases where several markers
are present at once (which pins down the precedence order).
"""

from __future__ import annotations

import json
import shutil

import pytest

from anyplace.cli.error_handler import GenerationError
from anyplace.core.build_runner import BuildRunner

try:
    from tests.helpers import write_files
except ImportError:  # pragma: no cover - depends on rootdir layout
    from helpers import write_files


def pkg(deps=None, dev_deps=None, scripts=None):
    body = {"name": "demo", "version": "1.0.0"}
    if deps:
        body["dependencies"] = deps
    if dev_deps:
        body["devDependencies"] = dev_deps
    if scripts:
        body["scripts"] = scripts
    return json.dumps(body)


def runner(tmp_path, files):
    root = write_files(tmp_path / "proj", files)
    return BuildRunner(root)


@pytest.fixture
def no_pip3(monkeypatch):
    """Force the pip fallback branch to be deterministic."""
    monkeypatch.setattr(shutil, "which", lambda name: None)


@pytest.fixture
def has_pip3(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)


# ---------------------------------------------------------------------------
# _detect_project_type -- one branch at a time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "files, expected",
    [
        ({"package.json": pkg(deps={"expo": "~50.0.0"})}, "expo-rn"),
        ({"package.json": pkg(deps={"next": "14.0.0"})}, "nextjs"),
        ({"package.json": pkg(dev_deps={"vite": "^5.0.0"})}, "react-vite"),
        ({"package.json": pkg(deps={"express": "^4.18.0"})}, "nodejs-backend"),
        ({"package.json": pkg(deps={"fastify": "^4.0.0"})}, "nodejs-backend"),
        ({"package.json": pkg(deps={"koa": "^2.0.0"})}, "nodejs-backend"),
        ({"package.json": pkg(deps={"hapi": "^20.0.0"})}, "nodejs-backend"),
        ({"package.json": pkg(deps={"lodash": "^4.0.0"})}, "nodejs"),
        ({"package.json": pkg()}, "nodejs"),
        ({"manage.py": "# django"}, "django"),
        ({"requirements.txt": "requests\n"}, "python"),
        ({"pyproject.toml": "[project]\nname='x'\n"}, "python"),
        ({"setup.py": "from setuptools import setup\n"}, "python"),
        ({"Cargo.toml": "[package]\nname='x'\n"}, "rust"),
        ({"go.mod": "module example.com/x\n"}, "go"),
        ({"README.md": "# nothing to build\n"}, "unknown"),
    ],
    ids=[
        "expo",
        "nextjs",
        "vite",
        "express",
        "fastify",
        "koa",
        "hapi",
        "plain_node_with_deps",
        "plain_node_no_deps",
        "django",
        "requirements_txt",
        "pyproject_toml",
        "setup_py",
        "rust",
        "go",
        "no_markers",
    ],
)
def test_detect_project_type_identifies_marker(tmp_path, files, expected):
    assert runner(tmp_path, files)._detect_project_type() == expected


def test_detect_project_type_returns_unknown_for_an_empty_directory(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert BuildRunner(empty)._detect_project_type() == "unknown"


def test_detect_project_type_finds_dependency_in_dev_dependencies(tmp_path):
    files = {"package.json": pkg(dev_deps={"expo": "~50.0.0"})}
    assert runner(tmp_path, files)._detect_project_type() == "expo-rn"


def test_detect_project_type_falls_back_to_nodejs_for_corrupt_package_json(tmp_path):
    files = {"package.json": "{ this is not json"}
    assert runner(tmp_path, files)._detect_project_type() == "nodejs"


# ---------------------------------------------------------------------------
# _detect_project_type -- documented precedence when markers collide
# ---------------------------------------------------------------------------


def test_detect_project_type_prefers_package_json_over_python_markers(tmp_path):
    files = {
        "package.json": pkg(deps={"express": "^4.0.0"}),
        "requirements.txt": "flask\n",
        "manage.py": "# django",
        "Cargo.toml": "[package]",
        "go.mod": "module x",
    }
    assert runner(tmp_path, files)._detect_project_type() == "nodejs-backend"


@pytest.mark.parametrize(
    "deps, expected",
    [
        ({"expo": "~50", "next": "14", "vite": "^5", "express": "^4"}, "expo-rn"),
        ({"next": "14", "vite": "^5", "express": "^4"}, "nextjs"),
        ({"vite": "^5", "express": "^4"}, "react-vite"),
    ],
    ids=["expo_wins", "next_beats_vite", "vite_beats_express"],
)
def test_detect_project_type_node_precedence_is_expo_next_vite_backend(
    tmp_path, deps, expected
):
    assert runner(tmp_path, {"package.json": pkg(deps=deps)})._detect_project_type() == expected


def test_detect_project_type_prefers_django_over_generic_python(tmp_path):
    files = {
        "manage.py": "# django",
        "requirements.txt": "django\n",
        "pyproject.toml": "[project]",
        "setup.py": "setup()",
    }
    assert runner(tmp_path, files)._detect_project_type() == "django"


def test_detect_project_type_prefers_python_over_rust_and_go(tmp_path):
    files = {
        "requirements.txt": "requests\n",
        "Cargo.toml": "[package]",
        "go.mod": "module x",
    }
    assert runner(tmp_path, files)._detect_project_type() == "python"


def test_detect_project_type_prefers_rust_over_go(tmp_path):
    files = {"Cargo.toml": "[package]", "go.mod": "module x"}
    assert runner(tmp_path, files)._detect_project_type() == "rust"


# ---------------------------------------------------------------------------
# get_build_command
# ---------------------------------------------------------------------------


def test_get_build_command_uses_expo_export_for_expo_projects(tmp_path):
    files = {"package.json": pkg(deps={"expo": "~50"}, scripts={"build": "x"})}
    assert runner(tmp_path, files).get_build_command() == ["npx", "expo", "export"]


@pytest.mark.parametrize(
    "deps", [{"vite": "^5"}, {"next": "14"}, {"express": "^4"}, {"lodash": "^4"}]
)
def test_get_build_command_runs_npm_build_when_the_script_exists(tmp_path, deps):
    files = {"package.json": pkg(deps=deps, scripts={"build": "x", "start": "y"})}
    assert runner(tmp_path, files).get_build_command() == ["npm", "run", "build"]


def test_get_build_command_falls_back_to_npm_start(tmp_path):
    files = {"package.json": pkg(deps={"express": "^4"}, scripts={"start": "node ."})}
    assert runner(tmp_path, files).get_build_command() == ["npm", "run", "start"]


def test_get_build_command_defaults_to_npm_build_without_any_scripts(tmp_path):
    files = {"package.json": pkg(deps={"vite": "^5"})}
    assert runner(tmp_path, files).get_build_command() == ["npm", "run", "build"]


@pytest.mark.parametrize(
    "files, expected",
    [
        ({"manage.py": "#"}, ["python3", "manage.py", "migrate", "--run-syncdb"]),
        ({"requirements.txt": "x\n"}, ["python3", "-m", "py_compile", "*.py"]),
        ({"Cargo.toml": "[package]"}, ["cargo", "build", "--release"]),
        ({"go.mod": "module x"}, ["go", "build", "./..."]),
    ],
    ids=["django", "python", "rust", "go"],
)
def test_get_build_command_per_non_node_project_type(tmp_path, files, expected):
    assert runner(tmp_path, files).get_build_command() == expected


def test_get_build_command_raises_for_an_undetectable_project(tmp_path):
    with pytest.raises(GenerationError) as excinfo:
        runner(tmp_path, {"notes.txt": "hello"}).get_build_command()
    assert "cannot detect project type" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# get_install_command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "deps",
    [{"expo": "~50"}, {"next": "14"}, {"vite": "^5"}, {"express": "^4"}, {"lodash": "^4"}],
    ids=["expo", "nextjs", "vite", "express", "plain_node"],
)
def test_get_install_command_uses_npm_with_legacy_peer_deps(tmp_path, deps):
    files = {"package.json": pkg(deps=deps)}
    assert runner(tmp_path, files).get_install_command() == [
        "npm",
        "install",
        "--legacy-peer-deps",
    ]


def test_get_install_command_uses_requirements_when_present(tmp_path, has_pip3):
    files = {"requirements.txt": "requests\n"}
    assert runner(tmp_path, files).get_install_command() == [
        "pip3",
        "install",
        "-r",
        "requirements.txt",
    ]


def test_get_install_command_falls_back_to_editable_install(tmp_path, has_pip3):
    files = {"pyproject.toml": "[project]\nname='x'\n"}
    assert runner(tmp_path, files).get_install_command() == ["pip3", "install", "-e", "."]


def test_get_install_command_uses_pip_when_pip3_is_absent(tmp_path, no_pip3):
    files = {"requirements.txt": "requests\n"}
    assert runner(tmp_path, files).get_install_command()[0] == "pip"


def test_get_install_command_for_django_uses_pip(tmp_path, has_pip3):
    files = {"manage.py": "#", "requirements.txt": "django\n"}
    assert runner(tmp_path, files).get_install_command() == [
        "pip3",
        "install",
        "-r",
        "requirements.txt",
    ]


@pytest.mark.parametrize(
    "files, expected",
    [
        ({"Cargo.toml": "[package]"}, ["cargo", "build"]),
        ({"go.mod": "module x"}, ["go", "mod", "download"]),
    ],
    ids=["rust", "go"],
)
def test_get_install_command_per_compiled_language(tmp_path, files, expected):
    assert runner(tmp_path, files).get_install_command() == expected


def test_get_install_command_raises_for_an_undetectable_project(tmp_path):
    with pytest.raises(GenerationError):
        runner(tmp_path, {"notes.txt": "hello"}).get_install_command()


# ---------------------------------------------------------------------------
# auto_install / auto_build -- must never raise
# ---------------------------------------------------------------------------


def test_auto_install_returns_false_for_an_undetectable_project(tmp_path):
    assert runner(tmp_path, {"notes.txt": "x"}).auto_install() is False


def test_auto_build_returns_false_for_an_undetectable_project(tmp_path):
    assert runner(tmp_path, {"notes.txt": "x"}).auto_build() is False


def test_auto_install_reports_a_missing_command_through_the_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    messages = []
    result = runner(tmp_path, {"package.json": pkg()}).auto_install(messages.append)

    assert result is False
    assert any("npm" in m for m in messages)


def test_auto_build_reports_a_missing_command_through_the_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    messages = []
    result = runner(tmp_path, {"Cargo.toml": "[package]"}).auto_build(messages.append)

    assert result is False
    assert any("cargo" in m for m in messages)


# ---------------------------------------------------------------------------
# run_build
# ---------------------------------------------------------------------------


def test_run_build_streams_output_and_returns_true_on_success(tmp_path, monkeypatch):
    br = runner(tmp_path, {"Cargo.toml": "[package]"})
    monkeypatch.setattr(br, "get_build_command", lambda: ["echo", "building"])

    lines = []
    assert br.run_build(lines.append) is True
    assert lines == ["building"]


def test_run_build_raises_generation_error_on_a_non_zero_exit(tmp_path, monkeypatch):
    br = runner(tmp_path, {"Cargo.toml": "[package]"})
    monkeypatch.setattr(br, "get_build_command", lambda: ["false"])

    with pytest.raises(GenerationError) as excinfo:
        br.run_build()
    assert "exit code" in str(excinfo.value)


def test_run_build_raises_generation_error_when_the_binary_is_missing(tmp_path, monkeypatch):
    br = runner(tmp_path, {"Cargo.toml": "[package]"})
    monkeypatch.setattr(br, "get_build_command", lambda: ["anyplace-no-such-binary"])

    with pytest.raises(GenerationError) as excinfo:
        br.run_build()
    assert "command not found" in str(excinfo.value).lower()


def test_build_runner_accepts_a_string_project_dir(tmp_path):
    root = write_files(tmp_path / "proj", {"go.mod": "module x"})
    assert BuildRunner(str(root))._detect_project_type() == "go"
