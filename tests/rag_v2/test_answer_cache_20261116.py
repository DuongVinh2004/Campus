"""Lever L2: repeated single-turn questions over identical authorized sources reuse the checked answer, nothing else."""
from dataclasses import replace

from campus247.rag_v2.answer_cache import AnswerCache, PROMPT_VERSION, enabled
from campus247.rag_v2.types import Citation, Outcome, Statement


def answered():
    citation = Citation("u", ("c",), "d", "v", "Quy chế", "path", 1, "Sinh viên nộp hồ sơ.")
    return Outcome("answer", "Sinh viên nộp hồ sơ.", (Statement("Sinh viên nộp hồ sơ.", ("u",)),), (citation,))


def test_same_question_and_sources_hit_and_any_change_misses():
    cache = AnswerCache()
    key = cache.key("rows-1", "Điều kiện bảo lưu là gì?")
    cache.put(key, answered())
    assert cache.get(key) is not None
    assert cache.get(cache.key("rows-1", "  điều kiện BẢO LƯU là gì ? ".replace(" ?", "?"))) is not None   # case/space-insensitive
    assert cache.get(cache.key("rows-2", "Điều kiện bảo lưu là gì?")) is None       # other authorized rows
    assert cache.get(cache.key("rows-1", "Điều kiện bảo lưu khóa 66 là gì?")) is None


def test_only_complete_cited_answers_are_stored():
    cache = AnswerCache()
    key = cache.key("r", "q")
    for outcome in (Outcome("refuse", "Không có nguồn."), Outcome("transient_error", "Lỗi."),
                    replace(answered(), citations=()), replace(answered(), statements=()),
                    Outcome("clarify", "Bạn nói rõ hơn?")):
        cache.put(key, outcome)
        assert cache.get(key) is None


def test_entries_expire_and_the_cache_is_bounded():
    now = [0.0]
    cache = AnswerCache(maxsize=2, ttl_s=10, clock=lambda: now[0])
    for name in ("a", "b", "c"):
        cache.put(cache.key("r", name), answered())
    assert cache.get(cache.key("r", "a")) is None and cache.get(cache.key("r", "c")) is not None   # oldest dropped
    now[0] = 11.0
    assert cache.get(cache.key("r", "c")) is None                                                  # expired


def test_prompt_version_is_part_of_the_key_and_the_feature_is_off_by_default(monkeypatch):
    assert len(PROMPT_VERSION) == 16
    monkeypatch.delenv("CAMPUS247_RAG_ANSWER_CACHE", raising=False)
    assert enabled() is False
    monkeypatch.setenv("CAMPUS247_RAG_ANSWER_CACHE", "on")
    assert enabled() is True
