"""The identifier branch survives authorization, and ranking is independent of the hash seed."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from campus247.rag_v2.adapters.memory_index import MemoryIndex
from campus247.rag_v2.adapters.runtime import AuthorizedIndex
from campus247.rag_v2.retrieval.bm25 import BM25
from campus247.rag_v2.retrieval.hybrid import retrieve
from campus247.rag_v2.understanding.analyze import analyze

from tests.rag_v2.retrieval.test_memory_index import make_unit


def _index(extra=0):
    units = [make_unit("noise", "quy định chung về học phí tín chỉ mã K72LAB " + "và " * 3),
             make_unit("target", "K72LAB phòng thí nghiệm mượn thiết bị")]
    units += [make_unit(f"rep{i}", "K72LAB nhắc lại mã trong tài liệu dài") for i in range(extra)]
    vectors = np.zeros((len(units), 2), dtype=np.float32)
    vectors[:, 0] = 1
    async def embed(query):
        raise RuntimeError("vector branch unavailable")
    index = MemoryIndex.__new__(MemoryIndex)
    index.manifest = {}
    index._initialize(tuple(units), vectors, embed)
    return index, {unit.unit_id: unit for unit in units}


def test_authorized_index_forwards_the_anchor_branch_with_the_same_grant():
    index, units = _index()
    view = AuthorizedIndex(index, {"target": units["target"]})
    direct = index.anchored("K72LAB", 5, allowed={"target"})
    assert direct and view.anchored("K72LAB", 5) == direct
    # Units outside the grant never appear.
    assert [uid for uid, _ in view.anchored("K72LAB", 5)] == ["target"]


def test_anchor_threshold_is_judged_inside_the_authorized_set():
    # 250 repeated units would exceed the old fixed threshold of 200 and switch the branch off.
    index, units = _index(extra=250)
    allowed = {"noise", "target"}
    ranked = index.anchored("K72LAB mượn thiết bị", 5, allowed=allowed)
    assert {uid for uid, _ in ranked} == allowed and ranked[0][0] == "target"
    # Still bounded: without an authorization narrowing the set, the code is not discriminating.
    docs = [(f"u{i}", "K72LAB nhắc lại") for i in range(250)]
    assert BM25(docs).anchored("K72LAB", 5) == []


@pytest.mark.asyncio
async def test_retrieval_through_authorization_keeps_the_anchored_unit_when_vector_is_down():
    index, units = _index(extra=40)
    view = AuthorizedIndex(index, {uid: unit for uid, unit in units.items() if uid in {"noise", "target"}})

    class NoRerank:
        async def rerank(self, query, texts, *, deadline_s):
            raise TimeoutError

    result = await retrieve(analyze("K72LAB mượn thiết bị", ()), view, NoRerank(),
                            lexical_k=1, vector_k=1, rerank_deadline_s=0.1, final_limit=5)
    assert "target" in [c.unit_id for c in result.candidates]


def test_bm25_ranking_does_not_depend_on_the_hash_seed():
    snippet = (
        "from campus247.rag_v2.retrieval.bm25 import BM25\n"
        "docs=[(str(i),' '.join(['a','b','c','d','e'][(i+j)%5] for j in range(5))+' '+('x'*(i%3))) for i in range(5)]\n"
        "docs=[(u,'alpha beta gamma delta epsilon '+t) for u,t in docs]\n"
        "docs=[(u,' '.join(sorted(t.split(), key=lambda w:(hash(w)*(int(u)+1))%7))) for u,t in docs]\n"
        "print([u for u,_ in BM25(docs).search('alpha beta gamma delta epsilon',5)])\n")
    root = Path(__file__).resolve().parents[3]
    src = str(root / "services" / "api" / "src")
    outputs = set()
    for seed in ("1", "2", "3", "4", "5", "6"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": src + os.pathsep + os.environ.get("PYTHONPATH", "")}
        outputs.add(subprocess.run([sys.executable, "-B", "-c", snippet], env=env, capture_output=True, text=True,
                                   check=True, cwd=root).stdout)
    assert len(outputs) == 1, outputs
