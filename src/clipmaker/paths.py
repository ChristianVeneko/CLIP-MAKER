"""Default data locations, anchored to the project root instead of the current directory."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """``$CLIPMAKER_HOME``, else the directory holding pyproject.toml, else the cwd."""
    env = os.environ.get("CLIPMAKER_HOME")
    if env:
        return Path(env).expanduser()
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def default_workdir() -> Path:
    return project_root() / "workdir"


def default_output() -> Path:
    return project_root() / "output"
