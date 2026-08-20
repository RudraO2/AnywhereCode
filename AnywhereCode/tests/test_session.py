"""Tests for anyplace.core.session. Everything happens under tmp_path."""

import json
import os
import stat

import pytest

from anyplace.core.session import (
    CURRENT_VERSION,
    MAX_RECENT,
    SessionState,
    SessionStore,
)


@pytest.fixture
def store(tmp_path):
    return SessionStore(tmp_path / "session.json")


def mode_of(path):
    return stat.S_IMODE(os.stat(str(path)).st_mode)


# --------------------------------------------------------------------------
# SessionState
# --------------------------------------------------------------------------

def test_default_state_has_empty_fields():
    state = SessionState()
    assert state.last_template == ""
    assert state.recent_projects == []
    assert state.saved_answers == {}
    assert state.run_count == 0
    assert state.version == CURRENT_VERSION


def test_state_round_trips_through_dict():
    state = SessionState(
        last_template="web-react-vite",
        last_provider="mock",
        last_project_name="runlog",
        last_mode="guided",
        recent_projects=["/a", "/b"],
        saved_answers={"idea": "x"},
        run_count=3,
    )
    assert SessionState.from_dict(state.to_dict()).to_dict() == state.to_dict()


def test_state_from_dict_coerces_wrong_types():
    state = SessionState.from_dict(
        {
            "last_template": 5,
            "recent_projects": "not a list",
            "saved_answers": ["nope"],
            "run_count": "7",
        }
    )
    assert state.last_template == "5"
    assert state.recent_projects == []
    assert state.saved_answers == {}
    assert state.run_count == 7


def test_state_from_dict_of_junk_returns_a_default():
    for junk in (None, [], "x", 3):
        assert SessionState.from_dict(junk) == SessionState()


def test_state_from_dict_caps_recent_projects():
    state = SessionState.from_dict(
        {"recent_projects": ["/p%d" % i for i in range(30)]}
    )
    assert len(state.recent_projects) == MAX_RECENT


# --------------------------------------------------------------------------
# load / save
# --------------------------------------------------------------------------

def test_load_with_no_file_returns_a_default_state(store):
    assert store.load() == SessionState()
    assert not store.path.exists()


def test_load_from_a_missing_directory_returns_a_default(tmp_path):
    store = SessionStore(tmp_path / "does" / "not" / "exist" / "session.json")
    assert store.load() == SessionState()


def test_save_then_load_round_trips(store):
    state = SessionState(
        last_template="mobile-expo-rn",
        last_provider="anthropic",
        last_mode="quick",
        saved_answers={"project_kind": "mobile"},
        run_count=2,
    )
    store.save(state)
    loaded = store.load()
    assert loaded.last_template == "mobile-expo-rn"
    assert loaded.last_provider == "anthropic"
    assert loaded.last_mode == "quick"
    assert loaded.saved_answers == {"project_kind": "mobile"}
    assert loaded.run_count == 2


def test_save_creates_missing_parent_directories(tmp_path):
    store = SessionStore(tmp_path / "deep" / "nested" / "session.json")
    store.save(SessionState(last_template="x"))
    assert store.path.exists()
    assert store.load().last_template == "x"


def test_save_stamps_updated_at_and_version(store):
    store.save(SessionState())
    loaded = store.load()
    assert loaded.updated_at.endswith("Z")
    assert loaded.version == CURRENT_VERSION


def test_saved_file_is_private_to_the_user(store):
    store.save(SessionState())
    assert mode_of(store.path) == 0o600


def test_saved_file_stays_private_after_a_rewrite(store):
    store.save(SessionState())
    os.chmod(str(store.path), 0o644)
    store.save(SessionState(last_template="y"))
    assert mode_of(store.path) == 0o600


def test_save_leaves_no_temp_files_behind(store):
    store.save(SessionState())
    store.save(SessionState(last_template="again"))
    leftovers = [p.name for p in store.path.parent.iterdir() if p.name != "session.json"]
    assert leftovers == []


def test_save_writes_valid_readable_json(store):
    store.save(SessionState(last_template="x"))
    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data["last_template"] == "x"


def test_save_accepts_a_plain_dict(store):
    store.save({"last_template": "from-dict"})
    assert store.load().last_template == "from-dict"


# --------------------------------------------------------------------------
# Degrading gracefully
# --------------------------------------------------------------------------

def test_corrupt_json_degrades_to_a_default(store):
    store.path.write_text("{ this is not json", encoding="utf-8")
    assert store.load() == SessionState()


def test_truncated_write_degrades_to_a_default(store):
    store.save(SessionState(last_template="x"))
    text = store.path.read_text(encoding="utf-8")
    store.path.write_text(text[: len(text) // 2], encoding="utf-8")
    assert store.load() == SessionState()


def test_empty_file_degrades_to_a_default(store):
    store.path.write_text("", encoding="utf-8")
    assert store.load() == SessionState()


def test_json_list_instead_of_object_degrades_to_a_default(store):
    store.path.write_text("[1, 2, 3]", encoding="utf-8")
    assert store.load() == SessionState()


def test_json_scalar_instead_of_object_degrades_to_a_default(store):
    store.path.write_text('"just a string"', encoding="utf-8")
    assert store.load() == SessionState()


def test_unknown_future_version_degrades_to_a_default(store):
    store.path.write_text(
        json.dumps({"version": CURRENT_VERSION + 5, "last_template": "from-the-future"}),
        encoding="utf-8",
    )
    assert store.load() == SessionState()


def test_a_directory_where_the_file_should_be_degrades_to_a_default(tmp_path):
    path = tmp_path / "session.json"
    path.mkdir()
    assert SessionStore(path).load() == SessionState()


def test_load_after_corruption_can_be_repaired_by_saving(store):
    store.path.write_text("garbage", encoding="utf-8")
    store.save(SessionState(last_template="repaired"))
    assert store.load().last_template == "repaired"


# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------

def test_update_merges_into_existing_state(store):
    store.update(last_template="web-react-vite")
    state = store.update(last_provider="mock")
    assert state.last_template == "web-react-vite"
    assert state.last_provider == "mock"
    assert store.load().last_template == "web-react-vite"


def test_update_merges_saved_answers_key_by_key(store):
    store.update(saved_answers={"idea": "x"})
    state = store.update(saved_answers={"project_kind": "web"})
    assert state.saved_answers == {"idea": "x", "project_kind": "web"}


def test_update_overwrites_a_repeated_saved_answer(store):
    store.update(saved_answers={"idea": "old"})
    state = store.update(saved_answers={"idea": "new"})
    assert state.saved_answers == {"idea": "new"}


def test_update_can_clear_saved_answers_with_none(store):
    store.update(saved_answers={"idea": "x"})
    assert store.update(saved_answers=None).saved_answers == {}


def test_update_ignores_unknown_fields(store):
    state = store.update(last_mode="guided", not_a_field="boom")
    assert state.last_mode == "guided"
    assert not hasattr(state, "not_a_field")


def test_update_coerces_run_count(store):
    assert store.update(run_count="4").run_count == 4


def test_update_persists_to_disk(store):
    store.update(last_project_name="runlog")
    assert SessionStore(store.path).load().last_project_name == "runlog"


def test_bump_run_count_increments_and_persists(store):
    assert store.bump_run_count().run_count == 1
    assert store.bump_run_count().run_count == 2
    assert store.load().run_count == 2


# --------------------------------------------------------------------------
# remember_project
# --------------------------------------------------------------------------

def test_remember_project_stores_a_resolved_absolute_path(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    project = tmp_path / "projects" / "runlog"
    project.mkdir(parents=True)
    state = store.remember_project(project)
    assert state.recent_projects == [str(project.resolve())]
    assert os.path.isabs(state.recent_projects[0])


def test_remember_project_puts_the_newest_first(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    store.remember_project(tmp_path / "a")
    store.remember_project(tmp_path / "b")
    recent = store.load().recent_projects
    assert recent[0].endswith("b")
    assert recent[1].endswith("a")


def test_remember_project_deduplicates_by_resolved_path(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    store.remember_project(tmp_path / "a")
    store.remember_project(tmp_path / "b")
    state = store.remember_project(tmp_path / "sub" / ".." / "a")
    assert len(state.recent_projects) == 2
    assert state.recent_projects[0] == str((tmp_path / "a").resolve())


def test_remember_project_caps_the_list_at_ten(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    for index in range(15):
        store.remember_project(tmp_path / ("p%02d" % index))
    recent = store.load().recent_projects
    assert len(recent) == MAX_RECENT
    assert recent[0].endswith("p14")
    assert recent[-1].endswith("p05")


def test_remember_project_accepts_a_string_path(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    state = store.remember_project(str(tmp_path / "a"))
    assert state.recent_projects[0] == str((tmp_path / "a").resolve())


def test_remember_project_seeds_the_last_project_name(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    assert store.remember_project(tmp_path / "runlog").last_project_name == "runlog"


def test_remember_project_keeps_other_state(tmp_path):
    store = SessionStore(tmp_path / "session.json")
    store.update(last_template="web-react-vite")
    state = store.remember_project(tmp_path / "a")
    assert state.last_template == "web-react-vite"


# --------------------------------------------------------------------------
# clear
# --------------------------------------------------------------------------

def test_clear_removes_the_file_and_resets_state(store):
    store.update(last_template="x")
    store.clear()
    assert not store.path.exists()
    assert store.load() == SessionState()


def test_clear_is_safe_when_there_is_nothing_to_clear(store):
    store.clear()
    store.clear()
    assert store.load() == SessionState()


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------

def test_store_accepts_a_string_path(tmp_path):
    store = SessionStore(str(tmp_path / "session.json"))
    store.save(SessionState(last_template="x"))
    assert store.load().last_template == "x"


def test_default_path_lives_in_the_config_dir(monkeypatch, tmp_path):
    import anyplace.config.environment as environment

    monkeypatch.setattr(environment, "get_config_dir", lambda: tmp_path)
    store = SessionStore()
    assert store.path == tmp_path / "session.json"
