"""Canonical paths and exclusively-created outputs for the integrated stage."""
import json
from pathlib import Path

from certificate_stage1_workspace import ROOT, checked

STATE = ROOT / "infra/local/multi-agent-integrated-20261013-01"


def retain(path, value):
    path = checked(path, STATE)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def stage_path(name):
    return checked(STATE / name, STATE)
