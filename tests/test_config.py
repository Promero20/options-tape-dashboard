"""Rutas configurables: variable de entorno > config.toml > valor por defecto."""

from tape_dashboard.config import REPO_ROOT, load_settings


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
