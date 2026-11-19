"""Negative checks for the static review parser; no network, models or runtime."""
import importlib.util
from pathlib import Path
import struct
import sys

import pytest

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("runtime_frontier_review", HERE / "runtime_frontier_review_20261004.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_version_specific_graph_does_not_conflate_optional_versions():
    graph = review.lock_graph([
        dict(name="router", version="1", dependencies=["sdk 2"]),
        dict(name="sdk", version="1"), dict(name="sdk", version="2", dependencies=["h2"]),
        dict(name="h2", version="3", dependencies=["sdk 2"]),
    ])
    assert review.shortest_path(graph, ("router", "1"), ("sdk", "1")) is None
    assert review.shortest_path(graph, ("router", "1"), ("h2", "3")) == ["router@1", "sdk@2", "h2@3"]


def test_ambiguous_lock_reference_is_rejected():
    with pytest.raises(AssertionError, match="ambiguous"):
        review.lock_graph([dict(name="router", version="1", dependencies=["sdk"]),
                           dict(name="sdk", version="1"), dict(name="sdk", version="2")])


def synthetic_elf():
    raw = bytearray(512)
    raw[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", raw, 18, 62)
    struct.pack_into("<Q", raw, 32, 64)
    struct.pack_into("<HH", raw, 54, 56, 2)
    struct.pack_into("<IIQQQQQQ", raw, 64, 1, 0, 0, 4096, 0, 512, 512, 1)
    struct.pack_into("<IIQQQQQQ", raw, 120, 2, 0, 176, 4272, 0, 64, 64, 8)
    for i, (tag, value) in enumerate([(5, 4400), (10, 20), (1, 1), (0, 0)]):
        struct.pack_into("<qQ", raw, 176 + i * 16, tag, value)
    raw[304:324] = b"\0libssl.so.3\0" + b"\0" * 7
    return raw


def test_dynamic_library_name_is_static_evidence():
    assert review.elf_dynamic(synthetic_elf()) == dict(needed=["libssl.so.3"], dynamic_section=True, rpath=[], runpath=[])


@pytest.mark.parametrize("mutation", ["wrong_machine", "bad_string_pointer", "out_of_bounds_segment", "bad_needed"])
def test_malformed_elf_rejected(mutation):
    raw = synthetic_elf()
    if mutation == "wrong_machine":
        struct.pack_into("<H", raw, 18, 3)
    elif mutation == "bad_string_pointer":
        struct.pack_into("<Q", raw, 184, 50000)
    elif mutation == "out_of_bounds_segment":
        struct.pack_into("<Q", raw, 152, 10000)
    else:
        struct.pack_into("<Q", raw, 216, 20)
    with pytest.raises(AssertionError):
        review.elf_dynamic(raw)
