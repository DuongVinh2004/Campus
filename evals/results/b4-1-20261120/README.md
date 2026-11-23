# B4.1: does retrieval work for English questions? (2026-11-20)

60 dev cases (every ~2nd of the 113 answerable cases with the clean wording), the question translated into English (by Claude, no provider call; proper names, programme and course codes kept), the **gold chunks identical** (checked in code). Index `data/rag_v2_index/embedded2`, production path (no rerank), embedding server 18081, no answer model.

| | Vietnamese | English |
|---|---|---|
| gold anywhere | 60/60 (100%) | 59/60 (98%) |
| in fused top 5 | 57/60 (95%) | 40/60 (67%) |
| in fused top 8 | 58/60 (97%) | 44/60 (73%) |
| in fused top 12 (what the generator reads) | 58/60 (97%) | 51/60 (85%) |
| in fused top 16 | 59/60 (98%) | 54/60 (90%) |

English reaches 73% / 85% of the Vietnamese rate at top 8 / 12 (design rule: continue to English *answers* only if recall@5 is at least 90% of Vietnamese; it is 70%). **Decision: stop at the English interface; answers stay Vietnamese (B4.5 not started).** The 8 cases that left the top 12 were all questions whose gold sits on codes or Vietnamese-only terms (lexical match lost). Cross-language retrieval could be improved (query translation before retrieval) but that changes retrieval, which is the owner's decision.

Files: `probe-vi.json`, `probe-en.json`; cases in `evals/datasets/rag-v2-en/` (`translations.jsonl` is the human-readable source).
