"""Tests for anyplace.core.git_manager.

These drive the real `git` binary inside tmp_path, so they are marked
`integration` and skip cleanly when git is unavailable.
"""

from __future__ import annotations

import subprocess

import pytest

from anyplace.cli.error_handler import GenerationError
from anyplace.core.git_manager import GitManager

pytestmark = pytest.mark.integration


@pytest.fixture
def manager(tmp_path):
    """A GitManager over an empty, un-initialised directory."""
    project = tmp_path / "project"
    project.mkdir()
    gm = GitManager(project)
    if not gm.check_git_installed():
        pytest.skip("git is not installed")
    return gm


def git_log(repo):
    return subprocess.run(
        ["git", "log", "--pretty=%s"], cwd=str(repo), capture_output=True, text=True
    ).stdout.splitlines()


# ---------------------------------------------------------------------------
# Construction / environment
# ---------------------------------------------------------------------------


def test_init_accepts_a_string_path(tmp_path):
    gm = GitManager(str(tmp_path))
    assert gm.project_dir == tmp_path


def test_repo_is_not_marked_initialized_before_init_repo(manager):
    assert manager.repo_initialized is False


def test_check_git_installed_reports_true_when_git_is_on_path(manager):
    assert manager.check_git_installed() is True


def test_check_git_installed_reports_false_when_git_is_missing(manager, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    assert manager.check_git_installed() is False


# ---------------------------------------------------------------------------
# init_repo
# ---------------------------------------------------------------------------


def test_init_repo_creates_a_git_directory(manager):
    assert manager.init_repo() is True
    assert (manager.project_dir / ".git").is_dir()
    assert manager.repo_initialized is True


def test_init_repo_sets_local_identity(manager):
    manager.init_repo()
    result = subprocess.run(
        ["git", "config", "--local", "user.name"],
        cwd=str(manager.project_dir),
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "AnywhereCode"


def test_init_repo_stays_initialized_when_config_fails(manager, monkeypatch):
    # Termux regression: `git config` right after `git init` can fail; that must
    # not undo the successful init.
    calls = []
    real = manager._run_git

    def fake(*args):
        calls.append(args)
        if args and args[0] == "config":
            raise GenerationError("fatal: not in a git directory")
        return real(*args)

    monkeypatch.setattr(manager, "_run_git", fake)
    assert manager.init_repo() is True
    assert manager.repo_initialized is True


def test_init_repo_raises_when_git_is_not_installed(manager, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    with pytest.raises(GenerationError) as excinfo:
        manager.init_repo()
    assert "git" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# create_gitignore
# ---------------------------------------------------------------------------


def test_create_gitignore_writes_the_file(manager):
    assert manager.create_gitignore() is True
    assert (manager.project_dir / ".gitignore").is_file()


@pytest.mark.parametrize(
    "entry", ["node_modules/", "__pycache__/", ".env", "dist/", ".logs/", ".anyplace/"]
)
def test_create_gitignore_includes_expected_entry(manager, entry):
    manager.create_gitignore()
    assert entry in (manager.project_dir / ".gitignore").read_text().splitlines()


def test_create_gitignore_works_without_an_initialised_repo(manager):
    assert manager.repo_initialized is False
    assert manager.create_gitignore() is True


def test_create_gitignore_returns_false_when_write_fails(manager):
    (manager.project_dir / ".gitignore").mkdir()  # a directory blocks the write
    assert manager.create_gitignore() is False


# ---------------------------------------------------------------------------
# add_and_commit
# ---------------------------------------------------------------------------


def test_add_and_commit_returns_false_without_an_initialised_repo(manager):
    (manager.project_dir / "a.txt").write_text("hi")
    assert manager.add_and_commit("a.txt", "add a") is False


def test_add_and_commit_creates_a_commit(manager):
    manager.init_repo()
    (manager.project_dir / "a.txt").write_text("hi")

    assert manager.add_and_commit("a.txt", "add a") is True
    assert git_log(manager.project_dir) == ["add a"]


def test_add_and_commit_returns_false_when_there_is_nothing_to_commit(manager):
    manager.init_repo()
    (manager.project_dir / "a.txt").write_text("hi")
    manager.add_and_commit("a.txt", "add a")

    assert manager.add_and_commit("a.txt", "again") is False
    assert git_log(manager.project_dir) == ["add a"]


def test_add_and_commit_returns_false_for_a_missing_file(manager):
    manager.init_repo()
    assert manager.add_and_commit("nope.txt", "add nope") is False


def test_add_and_commit_records_each_file_separately(manager):
    manager.init_repo()
    for name in ("a.txt", "b.txt"):
        (manager.project_dir / name).write_text(name)
        assert manager.add_and_commit(name, "add " + name) is True

    assert git_log(manager.project_dir) == ["add b.txt", "add a.txt"]


# ---------------------------------------------------------------------------
# commit_bulk
# ---------------------------------------------------------------------------


def test_commit_bulk_returns_false_without_an_initialised_repo(manager):
    assert manager.commit_bulk(["a.txt"], "bulk") is False


def test_commit_bulk_returns_false_for_an_empty_file_list(manager):
    manager.init_repo()
    assert manager.commit_bulk([], "bulk") is False


def test_commit_bulk_commits_every_file_in_one_commit(manager):
    manager.init_repo()
    names = ["a.txt", "b.txt", "c.txt"]
    for name in names:
        (manager.project_dir / name).write_text(name)

    assert manager.commit_bulk(names, "bulk commit") is True
    assert git_log(manager.project_dir) == ["bulk commit"]

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=str(manager.project_dir), capture_output=True, text=True
    ).stdout.split()
    assert sorted(tracked) == names


def test_commit_bulk_returns_false_when_a_file_is_missing(manager):
    manager.init_repo()
    (manager.project_dir / "a.txt").write_text("a")
    assert manager.commit_bulk(["a.txt", "ghost.txt"], "bulk") is False


# ---------------------------------------------------------------------------
# get_repo_status
# ---------------------------------------------------------------------------


def test_get_repo_status_returns_none_without_an_initialised_repo(manager):
    assert manager.get_repo_status() is None


def test_get_repo_status_is_empty_for_a_clean_repo(manager):
    manager.init_repo()
    (manager.project_dir / "a.txt").write_text("a")
    manager.add_and_commit("a.txt", "add a")
    assert manager.get_repo_status().strip() == ""


def test_get_repo_status_lists_untracked_files(manager):
    manager.init_repo()
    (manager.project_dir / "new.txt").write_text("x")
    assert "new.txt" in manager.get_repo_status()


def test_get_repo_status_lists_modified_files(manager):
    manager.init_repo()
    target = manager.project_dir / "a.txt"
    target.write_text("a")
    manager.add_and_commit("a.txt", "add a")
    target.write_text("changed")

    status = manager.get_repo_status()
    assert "a.txt" in status
    assert status.strip().startswith("M")


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------


def test_run_git_returns_stdout_on_success(manager):
    manager.init_repo()
    assert "git version" in manager._run_git("--version")


def test_run_git_raises_generation_error_in_a_non_repo_directory(manager):
    with pytest.raises(GenerationError) as excinfo:
        manager._run_git("status", "--short")
    assert "not a git repository" in str(excinfo.value).lower()


def test_run_git_raises_generation_error_for_an_unknown_subcommand(manager):
    manager.init_repo()
    with pytest.raises(GenerationError):
        manager._run_git("definitely-not-a-git-command")


def test_run_git_reports_a_missing_binary_with_install_hint(manager, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)
    with pytest.raises(GenerationError) as excinfo:
        manager._run_git("status")
    assert "not installed" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# git_repo fixture (shared with other agents)
# ---------------------------------------------------------------------------


def test_git_repo_fixture_has_one_commit(git_repo):
    assert (git_repo / ".git").is_dir()
    assert git_log(git_repo) == ["initial commit"]
    assert (git_repo / "README.md").is_file()


def test_git_manager_recognises_the_fixture_repo(git_repo):
    gm = GitManager(git_repo)
    gm.repo_initialized = True
    assert gm.get_repo_status().strip() == ""
