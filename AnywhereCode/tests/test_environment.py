"""Tests for anyplace.config.environment.

Platform detection is pure environment inspection, so every branch is driven
with monkeypatch. The autouse home sandbox in conftest guarantees the
directory-creating functions can only ever write inside tmp.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from anyplace.config import environment as env_mod

# Bound at import time (collection), i.e. before the autouse sandbox swaps the
# module attributes -- these are the genuine implementations.
from anyplace.config.environment import (
    get_config_dir,
    get_platform_info,
    get_projects_dir,
    is_termux,
)


@pytest.fixture
def not_termux(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.delenv("TERMUX_APP_PID", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)


# ---------------------------------------------------------------------------
# is_termux
# ---------------------------------------------------------------------------


def test_is_termux_false_on_a_plain_desktop(not_termux):
    assert is_termux() is False


def test_is_termux_true_when_termux_data_dir_exists(monkeypatch):
    monkeypatch.delenv("TERMUX_APP_PID", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.setattr(os.path, "exists", lambda p: p == "/data/data/com.termux")
    assert is_termux() is True


def test_is_termux_true_when_termux_app_pid_is_set(monkeypatch, not_termux):
    monkeypatch.setenv("TERMUX_APP_PID", "12345")
    assert is_termux() is True


def test_is_termux_true_for_empty_termux_app_pid(monkeypatch, not_termux):
    # os.environ.get(...) is not None -- an empty value still counts.
    monkeypatch.setenv("TERMUX_APP_PID", "")
    assert is_termux() is True


def test_is_termux_true_for_a_termux_prefix(monkeypatch, not_termux):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert is_termux() is True


def test_is_termux_false_for_an_unrelated_prefix(monkeypatch, not_termux):
    monkeypatch.setenv("PREFIX", "/usr/local")
    assert is_termux() is False


def test_is_termux_returns_a_real_bool(not_termux):
    assert isinstance(is_termux(), bool)


# ---------------------------------------------------------------------------
# get_projects_dir
# ---------------------------------------------------------------------------


def test_get_projects_dir_uses_dot_anyplace_on_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: False)
    monkeypatch.setenv("HOME", str(tmp_path))

    projects = get_projects_dir()
    assert projects == tmp_path / ".anyplace" / "projects"
    assert projects.is_dir()


def test_get_projects_dir_creates_the_desktop_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".anyplace").exists()

    get_projects_dir()
    assert (tmp_path / ".anyplace" / "projects").is_dir()


def test_get_projects_dir_prefers_termux_shared_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: True)
    monkeypatch.setenv("HOME", str(tmp_path))
    shared = tmp_path / "storage" / "downloads"
    shared.mkdir(parents=True)

    assert get_projects_dir() == shared


def test_get_projects_dir_falls_back_to_home_downloads_on_termux(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: True)
    monkeypatch.setenv("HOME", str(tmp_path))

    projects = get_projects_dir()
    assert projects == tmp_path / "Downloads"
    assert projects.is_dir()


def test_get_projects_dir_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert get_projects_dir() == get_projects_dir()


def test_get_projects_dir_returns_a_path(monkeypatch, tmp_path):
    monkeypatch.setattr(env_mod, "is_termux", lambda: False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert isinstance(get_projects_dir(), Path)


# ---------------------------------------------------------------------------
# get_config_dir
# ---------------------------------------------------------------------------


def test_get_config_dir_lives_under_dot_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert get_config_dir() == tmp_path / ".config" / "anyplace"


def test_get_config_dir_creates_the_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not (tmp_path / ".config").exists()

    assert get_config_dir().is_dir()


def test_get_config_dir_is_the_same_on_termux_and_desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(env_mod, "is_termux", lambda: True)
    on_termux = get_config_dir()
    monkeypatch.setattr(env_mod, "is_termux", lambda: False)
    assert get_config_dir() == on_termux


def test_get_config_dir_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert get_config_dir() == get_config_dir()


# ---------------------------------------------------------------------------
# get_platform_info
# ---------------------------------------------------------------------------


def test_get_platform_info_exposes_every_documented_key():
    info = get_platform_info()
    assert set(info) == {
        "system",
        "release",
        "machine",
        "is_termux",
        "projects_dir",
        "config_dir",
    }


def test_get_platform_info_reports_paths_as_strings():
    info = get_platform_info()
    assert isinstance(info["projects_dir"], str)
    assert isinstance(info["config_dir"], str)


def test_get_platform_info_reports_termux_flag_as_bool():
    assert isinstance(get_platform_info()["is_termux"], bool)


def test_get_platform_info_reflects_termux_detection(monkeypatch):
    monkeypatch.setattr(env_mod, "is_termux", lambda: True)
    assert get_platform_info()["is_termux"] is True


# ---------------------------------------------------------------------------
# The autouse sandbox itself
# ---------------------------------------------------------------------------


def test_sandbox_redirects_config_dir_into_a_temp_home(_sandbox_home):
    # Whatever anyplace thinks the config dir is, it must live under the
    # per-test temporary home, never the developer's real one.
    from anyplace.config.environment import get_config_dir as patched

    resolved = patched().resolve()
    assert str(resolved).startswith(str(_sandbox_home.resolve()))
    assert os.environ["HOME"] == str(_sandbox_home)


def test_sandbox_redirects_projects_dir_into_a_temp_home(_sandbox_home):
    from anyplace.config.environment import get_projects_dir as patched

    assert str(patched().resolve()).startswith(str(_sandbox_home.resolve()))


def test_sandbox_clears_termux_env_vars():
    assert "TERMUX_APP_PID" not in os.environ
    assert "PREFIX" not in os.environ
