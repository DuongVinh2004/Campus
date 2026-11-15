"""Approved 900-token pre-transport hook; no runtime launch or inference here."""
import json
import os
from pathlib import Path
import sys
import acceptance_continuation_20261005_10 as base
import continuation_audit as audit


class TokenEnvelopeError(ValueError):
    pass


class TokenEnvelope:
    def __init__(self):
        approved = json.loads((audit.HERE / "acceptance-20261007-25-adopted-token-envelope.json").read_text(encoding="utf-8"))
        assert approved["proposal_sha256"] == "b8bdd784979b7f1ceae70acd989487c069865001fa053c65a8d28ad6b7150de3"
        self.limit = approved["approved_envelope"]["input_tokens_per_item_max"]
        assert self.limit == 900
        if os.name == "nt":
            receipt = json.loads((audit.HERE / "acceptance-20261006-17-tokenizer-installed.json").read_text(encoding="utf-8"))
            for relative, expected in receipt["installed_hashes"].items():
                assert base.sha(audit.ROOT / relative) == expected
            site = audit.checked(Path(receipt["site_packages"]))
        else:
            # Linux: tokenizers 0.21.4 installed into its own directory, every file pinned by hash (installed 2026-11-15).
            receipt = json.loads((audit.HERE / "tokenizers-linux-20261115.json").read_text(encoding="utf-8"))
            assert receipt["schema"] == "tokenizers-linux-v1" and receipt["version"] == "0.21.4"
            site = audit.checked(audit.HERE / "tokenizers-linux-20261115")
            for relative, expected in receipt["hashes"].items():
                assert base.sha(site / relative) == expected
        sys.path.insert(0, str(site))
        import tokenizers
        assert tokenizers.__version__ == "0.21.4"
        assert audit.checked(Path(tokenizers.__file__)).is_relative_to(site)
        specs = {"embedding": ("bge-m3", "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08"),
            "reranker": ("bge-reranker-v2-m3", "69564b696052886ed0ac63fa393e928384e0f8caada38c1f4864a9bfbf379c15")}
        self.models = {}
        for kind, (directory, digest) in specs.items():
            path = audit.checked(audit.HERE / f"runtime-acquisition-20261004/{directory}/tokenizer.json")
            assert base.sha(path) == digest
            model = tokenizers.Tokenizer.from_file(str(path))
            model.no_truncation(); model.no_padding()
            self.models[kind] = model

    def count(self, kind, text, pair=None):
        if kind not in self.models or not isinstance(text, str) or (pair is not None and not isinstance(pair, str)):
            raise TokenEnvelopeError("Invalid token input")
        count = len(self.models[kind].encode(text, pair, add_special_tokens=True).ids)
        if count > self.limit:
            raise TokenEnvelopeError("Approved token envelope exceeded")
        return count

    async def before_request(self, request):
        # Runs as an httpx request hook before any bytes reach a transport.
        if request.url.scheme != "http" or request.url.host != "127.0.0.1" or request.url.port not in {18081, 18082}:
            raise TokenEnvelopeError("Unapproved runtime endpoint")
        if request.method == "GET" and request.url.path == "/info":
            return
        if request.method != "POST":
            raise TokenEnvelopeError("Unapproved runtime operation")
        try:
            payload = json.loads(request.content)
        except (ValueError, UnicodeDecodeError):
            raise TokenEnvelopeError("Invalid runtime payload") from None
        if not isinstance(payload, dict) or payload.get("truncate") is not False:
            raise TokenEnvelopeError("Truncation must remain disabled")
        if request.url.port == 18081 and request.url.path == "/embed":
            texts = payload.get("inputs")
            if not isinstance(texts, list) or len(texts) != 1:
                raise TokenEnvelopeError("One embedding item required")
            self.count("embedding", texts[0])
        elif request.url.port == 18082 and request.url.path == "/rerank":
            texts = payload.get("texts")
            if not isinstance(texts, list) or not 1 <= len(texts) <= 50:
                raise TokenEnvelopeError("Bounded reranking inputs required")
            for passage in texts:
                self.count("reranker", payload.get("query"), passage)
        else:
            raise TokenEnvelopeError("Unapproved runtime operation")
