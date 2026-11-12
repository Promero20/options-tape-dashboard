"""Rutas configurables: variable de entorno > config.toml > valor por defecto."""

import os

import pytest

from tape_dashboard.config import REPO_ROOT, load_env_file, load_settings, web_url


def test_defaults(tmp_path):
    settings = load_settings(config_file=tmp_path / "no-existe.toml", environ={})
    assert settings.data_dir == (REPO_ROOT.parent / "tape_data").resolve()
    assert settings.user_data_dir == (REPO_ROOT / "user_data").resolve()


def test_config_file_paths_are_relative_to_the_repo(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "otra/carpeta"\n', encoding="utf-8")
    settings = load_settings(config_file=config, environ={})
    assert settings.data_dir == (REPO_ROOT / "otra" / "carpeta").resolve()
    assert settings.user_data_dir == (REPO_ROOT / "user_data").resolve()


def test_environment_variables_take_precedence(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "otra"\nuser_data_dir = "otra2"\n', encoding="utf-8")
    environ = {"TAPE_DATA_DIR": str(tmp_path / "datos"), "TAPE_USER_DATA_DIR": str(tmp_path / "usuario")}
    settings = load_settings(config_file=config, environ=environ)
    assert settings.data_dir == (tmp_path / "datos").resolve()
    assert settings.user_data_dir == (tmp_path / "usuario").resolve()


def test_expected_hash_file_is_optional(tmp_path):
    assert load_settings(config_file=tmp_path / "no-existe.toml", environ={}).expected_hash_file is None

    config = tmp_path / "config.toml"
    config.write_text('[pipeline]\nexpected_hash_file = "docs/instructions.md"\n', encoding="utf-8")
    settings = load_settings(config_file=config, environ={})
    assert settings.expected_hash_file == (REPO_ROOT / "docs" / "instructions.md").resolve()

    settings = load_settings(config_file=config, environ={"TAPE_EXPECTED_HASH_FILE": str(tmp_path / "x.md")})
    assert settings.expected_hash_file == (tmp_path / "x.md").resolve()


def test_the_external_gex_reference_is_optional(tmp_path):
    missing = tmp_path / "no-existe.toml"
    assert load_settings(config_file=missing, environ={}).gex_reference_url is None
    assert load_settings(config_file=missing, environ={"GEX_REFERENCE_URL_SPX": "  "}).gex_reference_url is None
    url = "https://example.com/gex?symbol=SPX"
    settings = load_settings(config_file=missing, environ={"GEX_REFERENCE_URL_SPX": f" {url} "})
    assert settings.gex_reference_url == url


def test_a_env_file_fills_the_environment_without_overriding_it(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {key: value for key, value in os.environ.items()
                                        if key != "GEX_REFERENCE_URL_SPX"})
    os.environ["TAPE_TEST_ALREADY_SET"] = "from the environment"
    env_file = tmp_path / ".env"
    env_file.write_text("# a comment\nGEX_REFERENCE_URL_SPX=https://example.com/gex\n"
                        "TAPE_TEST_ALREADY_SET=from the file\n", encoding="utf-8")
    assert load_env_file(env_file) is True
    assert os.environ["GEX_REFERENCE_URL_SPX"] == "https://example.com/gex"
    assert os.environ["TAPE_TEST_ALREADY_SET"] == "from the environment"
    assert load_env_file(tmp_path / "missing.env") is False


@pytest.mark.parametrize("value, expected", [
    ("https://example.com/gex", "https://example.com/gex"),
    ("http://127.0.0.1:9000/gex?symbol=SPX", "http://127.0.0.1:9000/gex?symbol=SPX"),
    ("javascript:alert(1)", None),
    ("example.com/gex", None),
    ("ftp://example.com/gex", None),
    ("https://", None),
    ("", None),
    (None, None),
])
def test_only_web_addresses_are_used(value, expected):
    assert web_url(value) == expected
