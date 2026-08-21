"""Shared fixtures for the whole anyplace test-suite.

The single most important thing in this file is :func:`_sandbox_home`, an
autouse guard that makes it impossible for a test to read or write the
developer's real ``~/.config/anyplace`` or ``~/.anyplace/projects``.  It works
on two layers:

1. ``HOME`` / ``USERPROFILE`` are pointed at a per-test temporary directory, so
   ``Path.home()`` (and therefore every un-patched call into
   ``anyplace.config.environment``) resolves inside ``tmp``.
2. Every already-imported ``anyplace.*`` module that holds a reference to
   ``get_config_dir`` / ``get_projects_dir`` has that reference swapped for a
   tmp-backed replacement -- ``from x import y`` copies the function object, so
   patching the defining module alone would not be enough.

Other agents' test modules get this protection for free.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import requests

import anyplace.config.environment as env_mod
from anyplace.core.mock_llm import MockLLMProvider
from anyplace.core.plan_generator import FileInfo, ProjectPlan

try:  # works whether or not tests/ is a package
    from tests.helpers import write_files
except ImportError:  # pragma: no cover - depends on rootdir layout
    from helpers import write_files

# Captured at import time, before anything gets monkeypatched.
_REAL_GET_CONFIG_DIR = env_mod.get_config_dir
_REAL_GET_PROJECTS_DIR = env_mod.get_projects_dir


def _redirect_everywhere(monkeypatch, name, original, replacement):
    """Point every ``anyplace.*`` reference to ``original`` at ``replacement``."""
    monkeypatch.setattr(env_mod, name, replacement, raising=True)
    for module in list(sys.modules.values()):
        if module is None or module is env_mod:
            continue
        mod_name = getattr(module, "__name__", "")
        if not mod_name.startswith("anyplace"):
            continue
        if getattr(module, name, None) is original:
            monkeypatch.setattr(module, name, replacement, raising=False)


@pytest.fixture(autouse=True)
def _sandbox_home(tmp_path_factory, monkeypatch):
    """Autouse guard: no test may touch the developer's real home directory."""
    home = tmp_path_factory.mktemp("home")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    # Termux detection reads these; clear them so platform tests are deterministic.
    monkeypatch.delenv("TERMUX_APP_PID", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)

    config_dir = home / ".config" / "anyplace"
    projects_dir = home / ".anyplace" / "projects"

    def _sandboxed_config_dir():
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def _sandboxed_projects_dir():
        projects_dir.mkdir(parents=True, exist_ok=True)
        return projects_dir

    _redirect_everywhere(
        monkeypatch, "get_config_dir", _REAL_GET_CONFIG_DIR, _sandboxed_config_dir
    )
    _redirect_everywhere(
        monkeypatch, "get_projects_dir", _REAL_GET_PROJECTS_DIR, _sandboxed_projects_dir
    )
    return home


@pytest.fixture
def fake_config_dir(tmp_path, monkeypatch):
    """Redirect ``get_config_dir`` at an empty, test-owned directory.

    Layered on top of the autouse sandbox: use this when a test needs to know
    *exactly* which directory the config landed in.
    """
    config_dir = tmp_path / "config" / "anyplace"
    config_dir.mkdir(parents=True, exist_ok=True)

    def _config_dir():
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    monkeypatch.setattr(env_mod, "get_config_dir", _config_dir, raising=True)
    for module in list(sys.modules.values()):
        mod_name = getattr(module, "__name__", "")
        if mod_name.startswith("anyplace") and hasattr(module, "get_config_dir"):
            monkeypatch.setattr(module, "get_config_dir", _config_dir, raising=False)
    return config_dir


@pytest.fixture
def fake_projects_dir(tmp_path, monkeypatch):
    """Redirect ``get_projects_dir`` at an empty, test-owned directory."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    def _projects_dir():
        projects_dir.mkdir(parents=True, exist_ok=True)
        return projects_dir

    monkeypatch.setattr(env_mod, "get_projects_dir", _projects_dir, raising=True)
    for module in list(sys.modules.values()):
        mod_name = getattr(module, "__name__", "")
        if mod_name.startswith("anyplace") and hasattr(module, "get_projects_dir"):
            monkeypatch.setattr(module, "get_projects_dir", _projects_dir, raising=False)
    return projects_dir


@pytest.fixture
def tmp_project(tmp_path):
    """A temp dir holding a plausible generated project (react + vite shaped)."""
    root = tmp_path / "demo-project"
    write_files(
        root,
        {
            "package.json": (
                '{\n'
                '  "name": "demo-project",\n'
                '  "version": "0.1.0",\n'
                '  "scripts": {"build": "vite build", "dev": "vite"},\n'
                '  "dependencies": {"react": "^18.2.0"},\n'
                '  "devDependencies": {"vite": "^5.0.0"}\n'
                '}\n'
            ),
            "README.md": "# demo-project\n\nGenerated by AnywhereCode.\n",
            "src/main.tsx": "import App from './App';\n",
            "src/App.tsx": "export default function App() { return null; }\n",
            ".gitignore": "node_modules/\n",
        },
    )
    return root


@pytest.fixture
def mock_llm():
    """The project's own :class:`MockLLMProvider` -- no API key, no network."""
    return MockLLMProvider()


@pytest.fixture
def sample_plan():
    """A valid :class:`ProjectPlan` whose file dependencies all resolve."""
    files = [
        FileInfo(
            path="package.json",
            description="Project dependencies",
            file_type="config",
            dependencies=[],
        ),
        FileInfo(
            path="src/App.tsx",
            description="Root React component",
            file_type="source",
            dependencies=["package.json"],
        ),
        FileInfo(
            path="src/main.tsx",
            description="Application entry point",
            file_type="source",
            dependencies=["src/App.tsx", "package.json"],
        ),
        FileInfo(
            path="README.md",
            description="Project documentation",
            file_type="doc",
            dependencies=[],
        ),
    ]
    return ProjectPlan(
        project_name="demo-project",
        template="web-react-vite",
        description="A small React + Vite demo",
        tech_stack=["React", "Vite", "TypeScript"],
        files=files,
        key_features=["Component based", "Fast HMR"],
        estimated_time="10 minutes",
        architecture_notes="Single page app, no backend.",
        next_steps=["npm install", "npm run dev"],
    )


@pytest.fixture
def git_repo(tmp_path):
    """An initialised git repo with one committed file.

    Skips cleanly when git is unavailable or refuses to run.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    repo = tmp_path / "gitrepo"
    repo.mkdir()

    def run(*args):
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True
        )

    if run("init").returncode != 0:
        pytest.skip("git init failed in this environment")

    run("config", "--local", "user.email", "test@example.invalid")
    run("config", "--local", "user.name", "Anyplace Test")
    run("config", "--local", "commit.gpgsign", "false")

    (repo / "README.md").write_text("# fixture repo\n")
    run("add", "README.md")
    if run("commit", "-m", "initial commit").returncode != 0:
        pytest.skip("git commit failed in this environment")

    return repo


@pytest.fixture
def no_network(monkeypatch):
    """Make any accidental real HTTP call fail loudly instead of hanging CI."""

    def _boom(*args, **kwargs):
        raise AssertionError(
            "A test attempted a real network call: args=%r kwargs=%r" % (args, kwargs)
        )

    monkeypatch.setattr(requests, "post", _boom)
    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "request", _boom, raising=False)
    monkeypatch.setattr(requests.Session, "request", _boom, raising=False)
    return _boom
