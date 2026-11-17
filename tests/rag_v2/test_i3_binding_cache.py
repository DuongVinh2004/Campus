"""The per-turn source binding is proven once per unchanged row and re-proven when the row changes."""
from hashlib import sha256

import campus247.agent.nodes.rag_v2 as node
from campus247.rag_v2.types import Scope, Unit

BODY = "Sinh viên nộp hồ sơ bảo lưu tại phòng đào tạo."


def unit():
    return Unit("u1", ("c1",), "doc", "ver", "Quy chế", "quy_che", "clause", "Điều 1", 1, BODY, scope=Scope())


def row(content=BODY, title="Quy chế", sha=None, version="ver"):
    return {"chunk_id": "c1", "source_id": "doc", "document_version_id": version, "title": title,
            "section_path": "Điều 1", "content_text": content,
            "evidence_sha256": sha or sha256(content.encode()).hexdigest()}


def test_unchanged_row_is_hashed_once_and_stays_bound(monkeypatch):
    node._BOUND.clear()
    calls = []
    real = node.sha256
    monkeypatch.setattr(node, "sha256", lambda data: calls.append(1) or real(data))
    rows = {"c1": row()}
    assert [node._binding_failure(unit(), rows) for _ in range(5)] == [None] * 5
    assert len(calls) == 1


def test_a_changed_row_is_checked_again_and_fails_closed():
    node._BOUND.clear()
    assert node._binding_failure(unit(), {"c1": row()}) is None
    assert node._binding_failure(unit(), {"c1": row(title="Quy chế khác")}) == "title"
    assert node._binding_failure(unit(), {"c1": row(version="other")}) == "ids"
    # Same claimed hash, different text: the proof of the old text does not carry over.
    tampered = row(content=BODY + " Thêm điều khoản.", sha=sha256(BODY.encode()).hexdigest())
    assert node._binding_failure(unit(), {"c1": tampered}) == "hash"
    assert node._binding_failure(unit(), {}) == "row"


def test_a_realistic_working_set_stays_cached_between_turns(monkeypatch):
    """~48,000 (unit, chunk) pairs per turn: a bound below that clears the cache every turn."""
    node._BOUND.clear()
    pairs = 60_000
    for i in range(pairs):
        node._BOUND[(f"u{i}", "c1")] = ((), "")
    node._binding_failure(unit(), {"c1": row()})
    assert len(node._BOUND) >= pairs
    assert node._CACHE_LIMIT > pairs
    node._BOUND.clear()


def test_the_cache_is_bounded():
    node._BOUND.clear()
    for i in range(node._CACHE_LIMIT + 5):
        node._BOUND[(str(i), "c")] = ((), "")
    assert node._binding_failure(unit(), {"c1": row()}) is None
    assert len(node._BOUND) < node._CACHE_LIMIT
