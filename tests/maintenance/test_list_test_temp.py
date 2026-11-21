import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/maintenance/list_test_temp.py"
spec = importlib.util.spec_from_file_location("list_test_temp", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _make(root: Path, name: str, content: bytes = b"x" * 10) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / "a.txt").write_bytes(content)
    return folder


def test_scan_lists_only_matching_directories(tmp_path):
    _make(tmp_path, ".pytest-tmp-a")
    _make(tmp_path, "src")
    (tmp_path / ".pytest-tmp-file").write_text("not a directory")
    rows = module.scan(tmp_path)
    assert [row["name"] for row in rows] == [".pytest-tmp-a"]
    assert rows[0]["bytes"] == 10 and rows[0]["readable"] is True


def test_default_mode_never_deletes(tmp_path):
    folder = _make(tmp_path, ".pytest-tmp-a")
    assert module.main(["--root", str(tmp_path)]) == 0
    assert folder.exists()


def test_delete_requires_listed_names_and_strict_pattern(tmp_path):
    keep = _make(tmp_path, "important")
    drop = _make(tmp_path, ".pytest-tmp-a")
    other = _make(tmp_path, ".pytest-tmp-b")
    listing = tmp_path / "list.csv"
    listing.write_text("name,bytes,modified,readable\n.pytest-tmp-a,10,x,True\nimportant,1,x,True\n..\\evil,1,x,True\n", encoding="utf-8")
    deleted, refused = module.delete_listed(tmp_path, listing)
    assert deleted == [".pytest-tmp-a"]
    assert set(refused) == {"important", "..\\evil"}
    assert keep.exists() and other.exists() and not drop.exists()


def test_delete_refuses_links(tmp_path):
    target = _make(tmp_path, "real")
    link = tmp_path / ".pytest-tmp-link"
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    listing = tmp_path / "list.csv"
    listing.write_text("name\n.pytest-tmp-link\n", encoding="utf-8")
    deleted, refused = module.delete_listed(tmp_path, listing)
    assert deleted == [] and refused == [".pytest-tmp-link"]
    assert (target / "a.txt").exists()


def test_a_directory_that_cannot_be_removed_does_not_stop_the_others(tmp_path, monkeypatch, capsys):
    locked = _make(tmp_path, ".pytest-tmp-locked")
    easy = _make(tmp_path, ".pytest-tmp-easy")
    listing = tmp_path / "list.csv"
    listing.write_text("name,bytes,modified,readable\n.pytest-tmp-locked,10,x,False\n.pytest-tmp-easy,10,x,True\n", encoding="utf-8")
    real = module.shutil.rmtree

    def rmtree(path, *args, **kwargs):
        if Path(path).name == ".pytest-tmp-locked":
            raise PermissionError(5, "Access is denied", str(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", rmtree)
    deleted, refused = module.delete_listed(tmp_path, listing)
    assert deleted == [".pytest-tmp-easy"] and refused == []
    assert module.LAST_FAILED == [".pytest-tmp-locked"]
    assert locked.exists() and not easy.exists()
    assert module.main(["--root", str(tmp_path), "--delete", str(listing)]) == 1  # locked one still reported as a failure
    assert "failed: .pytest-tmp-locked" in capsys.readouterr().out
