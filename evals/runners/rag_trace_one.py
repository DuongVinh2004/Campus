"""Answer one question in process with the runtime's own models and print every model exchange and the outcome.

For finding why one answer went wrong: the HTTP API returns the outcome only, this shows what the generator was given (each
source with its heading), what it wrote, what the checks dropped and why (`statement_rejections`), and the final outcome.
It uses the running runtime's gateway sidecar (8025, its token file, budget and accounting), embedder (18081) and reranker
(18082), and the served index; nothing is written. The API path adds the intent router's restatement and the conversation
layer before this point: when the two disagree, compare with evals/runners/rag_natural_eval.py against 8015.

  PYTHONPATH=data/rag_v2_vendor infra/local/rag-fixture/.venv/Scripts/python.exe -B evals/runners/rag_trace_one.py \
      "question" ["earlier user turn" ...] [--index data/rag_v2_index/embedded2] [--gateway http://127.0.0.1:8025]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "scripts"), str(ROOT)]

TOKEN = ROOT / "infra/local/public-rag-20261013/gateway-sidecar.token"


class Tap:
    """Passes every request to the real gateway and prints the request and the response."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    async def generate(self, request):
        self.calls += 1
        response = await self.inner.generate(request)
        print(f"\n----- model call {self.calls}: request -----\n{request}")
        print(f"----- model call {self.calls}: response -----\n{getattr(response, 'output_text', response)}")
        return response


async def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("history", nargs="*", help="earlier user turns, oldest first")
    parser.add_argument("--index", default="data/rag_v2_index/embedded2")
    parser.add_argument("--gateway", default="http://127.0.0.1:8025")
    args = parser.parse_args(argv)

    import knowledge_platform
    from campus247.infrastructure.llm.remote_gateway import RemoteGateway, read_token
    from campus247.rag_v2.adapters.http_reranker import HTTPReranker
    from campus247.rag_v2.adapters.index_store import read_index
    from campus247.rag_v2.adapters.memory_index import MemoryIndex
    from campus247.rag_v2.service import RagV2Service
    from campus247.rag_v2.vocabulary import Vocabulary

    embedding, _ = knowledge_platform.models()

    async def embed(query):
        return (await embedding._embed((query,))).vectors[0].values

    snapshot = read_index(ROOT / args.index)
    index = MemoryIndex.__new__(MemoryIndex)   # the same construction as campus247.bootstrap.rag_v2.load_rag_v2
    index.manifest = snapshot.manifest
    index._initialize(snapshot.units, snapshot.embeddings, embed)
    service = RagV2Service(snapshot.facts, Vocabulary.from_units(snapshot.units))
    gateway = Tap(RemoteGateway(args.gateway, read_token(str(TOKEN))))
    outcome = await service.answer(args.question, tuple(args.history), gateway=gateway, index=index,
                                   reranker=HTTPReranker(batch_size=10), embed=embed)
    print("\n===== outcome =====")
    print(json.dumps({key: str(value)[:2000] for key, value in vars(outcome).items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
