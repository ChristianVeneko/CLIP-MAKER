from pathlib import Path

from clipmaker import paths


def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPMAKER_HOME", str(tmp_path))
    assert paths.project_root() == tmp_path
    assert paths.default_workdir() == tmp_path / "workdir"
    assert paths.default_output() == tmp_path / "output"


def test_root_is_repo_root_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("CLIPMAKER_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    root = paths.project_root()
    assert (root / "pyproject.toml").is_file()
    assert root.is_absolute()


def test_falls_back_to_cwd_without_pyproject(tmp_path, monkeypatch):
    monkeypatch.delenv("CLIPMAKER_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paths, "__file__", str(tmp_path / "pkg" / "paths.py"))
    assert paths.project_root() == Path.cwd()


def test_cli_and_web_defaults_are_anchored(monkeypatch, tmp_path):
    from clipmaker.cli import build_parser
    from clipmaker.web.app import Settings

    monkeypatch.setenv("CLIPMAKER_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path / "..")
    args = build_parser().parse_args(["serve"])
    assert args.workdir == tmp_path / "workdir" and args.output == tmp_path / "output"
    s = Settings()
    assert s.workdir == tmp_path / "workdir" and s.output_dir == tmp_path / "output"
