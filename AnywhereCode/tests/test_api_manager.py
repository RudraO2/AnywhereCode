"""Tests for anyplace.config.api_manager.

Every APIManager here is built against `fake_config_dir`, so the developer's
real ~/.config/anyplace/config.yaml is never read or written.
"""

from __future__ import annotations

import stat

import pytest
import yaml

from anyplace.cli.error_handler import ConfigError
from anyplace.config.api_manager import APIManager

KEYS = {
    "claude": "sk-ant-api03-testkey",
    "gemini": "AIzaSyTestKey1234567890",
    "openrouter": "sk-or-v1-testkey",
    "custom": "some-long-custom-key",
}


@pytest.fixture
def manager(fake_config_dir):
    return APIManager()


def config_on_disk(config_dir):
    return yaml.safe_load((config_dir / "config.yaml").read_text())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_init_points_at_the_configured_config_dir(manager, fake_config_dir):
    assert manager.config_dir == fake_config_dir
    assert manager.config_file == fake_config_dir / "config.yaml"
    assert manager.get_config_file_path() == fake_config_dir / "config.yaml"


def test_init_starts_empty_when_no_config_file_exists(manager):
    assert manager.config == {"providers": {}}
    assert manager.list_providers() == {}


def test_init_does_not_create_a_config_file(manager, fake_config_dir):
    assert not (fake_config_dir / "config.yaml").exists()


def test_init_treats_an_empty_config_file_as_no_providers(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text("")
    assert APIManager().config == {"providers": {}}


def test_init_reads_an_existing_config_file(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text(
        yaml.dump({"providers": {"claude": {"api_key": "sk-ant-x", "model": "m"}}})
    )
    assert APIManager().get_provider("claude") == {"api_key": "sk-ant-x", "model": "m"}


def test_init_raises_config_error_for_invalid_yaml(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text("providers: {claude: [unclosed\n")
    with pytest.raises(ConfigError) as excinfo:
        APIManager()
    assert "yaml" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "body", ["just a bare string\n", "- one\n- two\n", "42\n"],
    ids=["scalar", "list", "number"],
)
def test_init_rejects_a_config_file_that_is_not_a_mapping(fake_config_dir, body):
    (fake_config_dir / "config.yaml").write_text(body)
    with pytest.raises(ConfigError) as excinfo:
        APIManager()
    assert "mapping" in str(excinfo.value).lower()


def test_init_rejects_a_providers_key_that_is_not_a_mapping(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text("providers:\n  - claude\n")
    with pytest.raises(ConfigError) as excinfo:
        APIManager()
    assert "providers" in str(excinfo.value).lower()


def test_init_supplies_an_empty_providers_map_when_the_key_is_missing(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text("active_provider: claude\n")
    assert APIManager().list_providers() == {}


def test_init_supplies_an_empty_providers_map_when_the_key_is_null(fake_config_dir):
    (fake_config_dir / "config.yaml").write_text("providers:\n")
    assert APIManager().list_providers() == {}


# ---------------------------------------------------------------------------
# set_provider / get_provider
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", sorted(KEYS))
def test_set_provider_round_trips_through_disk(manager, fake_config_dir, provider):
    manager.set_provider(provider, KEYS[provider], "some-model")

    reloaded = APIManager()
    assert reloaded.get_provider(provider) == {
        "api_key": KEYS[provider],
        "model": "some-model",
    }


def test_set_provider_stores_extra_keyword_settings(manager):
    manager.set_provider(
        "custom", KEYS["custom"], "m", base_url="http://localhost:9000/v1"
    )
    assert APIManager().get_provider("custom")["base_url"] == "http://localhost:9000/v1"


def test_set_provider_lowercases_the_provider_name(manager):
    manager.set_provider("CLAUDE", KEYS["claude"], "m")
    assert "claude" in APIManager().list_providers()


def test_get_provider_is_case_insensitive(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    assert manager.get_provider("CLAUDE") == manager.get_provider("claude")


def test_get_provider_returns_none_for_an_unknown_provider(manager):
    assert manager.get_provider("nope") is None


def test_set_provider_replaces_an_earlier_configuration(manager):
    manager.set_provider("claude", KEYS["claude"], "old-model")
    manager.set_provider("claude", KEYS["claude"], "new-model")
    assert APIManager().get_provider("claude")["model"] == "new-model"


def test_set_provider_keeps_other_providers(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_provider("gemini", KEYS["gemini"], "m")
    assert sorted(APIManager().list_providers()) == ["claude", "gemini"]


@pytest.mark.parametrize(
    "provider, bad_key",
    [
        ("claude", "sk-wrong-prefix"),
        ("gemini", "not-a-google-key"),
        ("openrouter", "sk-ant-wrong"),
        ("custom", "short"),
        ("claude", ""),
        ("claude", "   "),
    ],
)
def test_set_provider_rejects_a_badly_shaped_key(manager, provider, bad_key):
    with pytest.raises(ConfigError):
        manager.set_provider(provider, bad_key, "m")


def test_set_provider_does_not_write_anything_when_the_key_is_rejected(
    manager, fake_config_dir
):
    with pytest.raises(ConfigError):
        manager.set_provider("claude", "nope", "m")
    assert not (fake_config_dir / "config.yaml").exists()


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------


def test_saved_config_is_only_readable_by_its_owner(manager, fake_config_dir):
    manager.set_provider("claude", KEYS["claude"], "m")
    mode = stat.S_IMODE((fake_config_dir / "config.yaml").stat().st_mode)
    assert mode == 0o600


def test_saved_config_stays_0600_after_a_rewrite(manager, fake_config_dir):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_provider("gemini", KEYS["gemini"], "m")
    mode = stat.S_IMODE((fake_config_dir / "config.yaml").stat().st_mode)
    assert mode == 0o600


def test_saved_config_is_plain_readable_yaml(manager, fake_config_dir):
    manager.set_provider("claude", KEYS["claude"], "m")
    assert config_on_disk(fake_config_dir)["providers"]["claude"]["model"] == "m"


# ---------------------------------------------------------------------------
# Active provider selection
# ---------------------------------------------------------------------------


def test_get_active_provider_is_none_before_anything_is_configured(manager):
    assert manager.get_active_provider() is None


def test_set_active_provider_persists_the_choice(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_provider("gemini", KEYS["gemini"], "m")
    manager.set_active_provider("gemini")

    assert APIManager().get_active_provider() == "gemini"


def test_set_active_provider_lowercases_the_name(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_active_provider("Claude")
    assert manager.get_active_provider() == "claude"


def test_set_active_provider_rejects_an_unconfigured_provider(manager):
    with pytest.raises(ConfigError) as excinfo:
        manager.set_active_provider("gemini")
    assert "gemini" in str(excinfo.value)


def test_get_active_config_returns_the_selected_provider(manager):
    manager.set_provider("claude", KEYS["claude"], "claude-model")
    manager.set_provider("gemini", KEYS["gemini"], "gemini-model")
    manager.set_active_provider("gemini")

    assert manager.get_active_config()["model"] == "gemini-model"


def test_get_active_config_falls_back_to_the_only_provider(manager):
    manager.set_provider("claude", KEYS["claude"], "claude-model")
    assert manager.get_active_config()["api_key"] == KEYS["claude"]


def test_get_active_config_raises_when_nothing_is_configured(manager):
    with pytest.raises(ConfigError) as excinfo:
        manager.get_active_config()
    assert "no llm provider" in str(excinfo.value).lower()


def test_get_active_config_raises_when_active_provider_was_removed(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_active_provider("claude")
    manager.config["providers"] = {}

    with pytest.raises(ConfigError) as excinfo:
        manager.get_active_config()
    assert "claude" in str(excinfo.value)


# ---------------------------------------------------------------------------
# validate_provider_config
# ---------------------------------------------------------------------------


def test_validate_provider_config_true_for_a_complete_entry(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    assert manager.validate_provider_config("claude") is True


def test_validate_provider_config_false_for_an_unknown_provider(manager):
    assert manager.validate_provider_config("claude") is False


@pytest.mark.parametrize(
    "entry",
    [{"api_key": "sk-ant-x"}, {"model": "m"}, {"api_key": "", "model": "m"},
     {"api_key": "sk-ant-x", "model": ""}, {}],
    ids=["no_model", "no_key", "blank_key", "blank_model", "empty"],
)
def test_validate_provider_config_false_for_an_incomplete_entry(manager, entry):
    manager.config["providers"]["claude"] = entry
    assert manager.validate_provider_config("claude") is False


# ---------------------------------------------------------------------------
# reset_config
# ---------------------------------------------------------------------------


def test_reset_config_clears_every_provider(manager):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.set_active_provider("claude")
    manager.reset_config()

    assert manager.config == {"providers": {}}
    assert manager.get_active_provider() is None


def test_reset_config_is_persisted_to_disk(manager, fake_config_dir):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.reset_config()

    assert config_on_disk(fake_config_dir) == {"providers": {}}
    assert APIManager().list_providers() == {}


def test_reset_config_keeps_the_file_permissions_locked_down(manager, fake_config_dir):
    manager.set_provider("claude", KEYS["claude"], "m")
    manager.reset_config()
    mode = stat.S_IMODE((fake_config_dir / "config.yaml").stat().st_mode)
    assert mode == 0o600


def test_reset_config_works_before_anything_was_saved(manager, fake_config_dir):
    manager.reset_config()
    assert (fake_config_dir / "config.yaml").exists()


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_save_raises_config_error_when_the_file_cannot_be_written(
    manager, fake_config_dir, monkeypatch
):
    import builtins

    real_open = builtins.open

    def blocked(path, mode="r", *args, **kwargs):
        if str(path).endswith("config.yaml") and "w" in mode:
            raise IOError("read-only filesystem")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", blocked)
    with pytest.raises(ConfigError) as excinfo:
        manager.set_provider("claude", KEYS["claude"], "m")
    assert "save" in str(excinfo.value).lower()
