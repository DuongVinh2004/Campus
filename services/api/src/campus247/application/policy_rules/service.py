"""F2.3/F2.5: draft -> validate -> review -> publish (preview + confirm) of policy rules, public evaluation, staleness."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from campus247.domain.policy_rules import engine
from campus247.domain.policy_rules.rule import canonical_sha256, source_hashes, structural_issues, verbatim_issues
from campus247.domain.policy_rules.variables import Vocabulary
from campus247.domain.policy_rules.verify import check_vectors, generate_vectors, input_variables
from campus247.ports.policy_rules import Conflict
from campus247.ports.campus_ops import OpsError, uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

AUTHOR_ROLES = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.KNOWLEDGE_CONTRIBUTOR, IdentityRole.SYSTEM_ADMIN}
REVIEW_ROLES = {IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SYSTEM_ADMIN}
PREVIEW_TTL = timedelta(minutes=10)
GOLD_MIN_MATCH = 0.98


class PolicyInputInvalid(OpsError):
    def __init__(self, errors: list[dict]):
        super().__init__(422, "POLICY_INPUT_INVALID", "Dữ liệu nhập không hợp lệ.")
        self.errors = errors


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


class PolicyRulesService:
    def __init__(self, store, vocab: Vocabulary, text_of_unit: Callable[[str], str | None],
                 release: Callable[[], dict] | None = None, *, clock: Callable[[], datetime] | None = None,
                 signing_key: str = "dev-policy-rules-key", enabled: Callable[[str], bool] | None = None):
        self.store, self.vocab, self.text_of_unit = store, vocab, text_of_unit
        self.release = release or (lambda: {"release_id": "unknown", "binding_sha256": "unknown"})
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._key = signing_key.encode()
        self.enabled = enabled or (lambda key: True)

    # ------------------------------------------------------------------ roles
    @staticmethod
    def _roles(actor: IdentityContext) -> set:
        return set(actor.roles)

    def require_author(self, actor: IdentityContext) -> None:
        if not AUTHOR_ROLES & self._roles(actor):
            raise OpsError(403, "FORBIDDEN", "Chỉ cán bộ tri thức mới soạn được luật.")

    def require_reviewer(self, actor: IdentityContext) -> None:
        if not REVIEW_ROLES & self._roles(actor):
            raise OpsError(403, "FORBIDDEN", "Chỉ quản trị tri thức mới duyệt được luật.")

    # ------------------------------------------------------------------ records for the engine
    def records(self) -> list[dict]:
        return [{"body": r["body"], "version": r["version"], "status": r["status"], "content_sha256": r["content_sha256"],
                 "release_id": r["release_id"], "graph_version": r["graph_version"]} for r in self.store.current_records()]

    # ------------------------------------------------------------------ public
    def topics(self) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for r in self.records():
            if r["status"] == "PUBLISHED":
                groups.setdefault(r["body"]["topic"], []).append(r)
        out = []
        for topic, recs in sorted(groups.items()):
            first = recs[0]["body"]
            eff = [r["body"]["applies"]["effective"].get("from") for r in recs if (r["body"].get("applies") or {}).get("effective", {}).get("from")]
            out.append({"topic": topic, "label": first["conclusion"]["label"], "description": first.get("description", ""),
                        "rule_count": len(recs), "effective_from": min(eff) if eff else None,
                        "cohorts": [r["body"]["applies"].get("cohorts") for r in recs]})
        return out

    def form(self, topic: str, as_of=None, cohort=None, program=None) -> dict:
        chosen, _ = engine.select_rules(self.records(), topic, as_of, cohort, program)
        if not chosen:
            raise OpsError(404, "POLICY_TOPIC_NOT_FOUND", "Chưa có luật cho chủ đề này.")
        fields, seen = [], set()
        for rec in chosen:
            for node in _walk_preds(rec["body"]["when"]):
                var = self.vocab.get(node["pred"]["var"])
                if var is None:
                    continue
                keys = [var.key] if not self.vocab.expr(var.key) else list(self.vocab.base_variables(var.key))
                for key in keys:
                    if key in seen:
                        continue
                    seen.add(key)
                    v = self.vocab.get(key)
                    fields.append({"var": key, "label": v.label, "type": v.type, "unit": v.unit, "min": v.min, "max": v.max,
                        "step": v.grid_step if v.numeric else None, "values": list(v.values), "input": v.input,
                        "help": v.help, "source": {"path": (node.get("source") or {}).get("path")}})
        return {"topic": topic, "fields": fields, "conclusion": chosen[0]["body"]["conclusion"]["label"],
                "needs_cohort": any(((r["body"].get("applies") or {}).get("cohorts") or {}).get("from") or
                    ((r["body"].get("applies") or {}).get("cohorts") or {}).get("to") for r in chosen)}

    def evaluate(self, topic: str, inputs: dict, *, as_of=None, cohort=None, program=None) -> dict:
        clean, errors = self.vocab.validate_inputs(inputs or {})
        if errors:
            raise PolicyInputInvalid(errors)
        result = engine.evaluate(self.vocab, self.records(), topic, clean, as_of=as_of, cohort=cohort, program=program)
        self.store.bump(datetime.now(engine.VN).date().isoformat(), topic, result["outcome"])
        return result

    def what_if(self, topic: str, inputs: dict, vary: str, *, as_of=None, cohort=None, program=None, points: int = 11) -> dict:
        clean, errors = self.vocab.validate_inputs(inputs or {})
        var = self.vocab.get(vary)
        if var is None or not var.numeric:
            errors.append({"var": vary, "code": "NOT_VARIABLE_NUMERIC"})
        if errors:
            raise PolicyInputInvalid(errors)
        return engine.what_if(self.vocab, self.records(), topic, clean, vary, points, as_of=as_of, cohort=cohort, program=program)

    # ------------------------------------------------------------------ validation of a rule body
    def validate_body(self, body: dict, *, with_vectors: bool = True) -> dict:
        issues = structural_issues(body, self.vocab)
        if not issues:
            issues += verbatim_issues(body, self.text_of_unit)
        vectors, mismatches = [], []
        if with_vectors and not issues:
            vectors = generate_vectors(self.vocab, body)
            mismatches = check_vectors(self.vocab, body, vectors)
        for ex in body.get("exceptions") or ():
            if not any(r["body"]["rule_id"] == ex.get("rule_id") for r in self.records()):
                issues.append({"code": "EXCEPTION_RULE_UNKNOWN", "target": ex.get("rule_id")})
        return {"issues": issues, "vectors": vectors, "mismatches": mismatches, "variables": input_variables(self.vocab, body) if not issues else []}

    @staticmethod
    def gold_report(vectors: list[dict]) -> dict:
        gold = [v for v in vectors if v["origin"] == "GOLD_MODEL"]
        agree = [v for v in gold if v.get("verdict") in {None, "MATCH"}]
        pending = [v for v in gold if v.get("verdict") == "MISMATCH"]
        decided = [v for v in gold if v.get("verdict") in {"RULE_FIX_NEEDED", "CASE_INVALID"}]
        return {"total": len(gold), "match": len(agree), "mismatch_pending": len(pending), "decided": len(decided),
                "rate": (len(agree) / (len(gold) - len([v for v in decided if v["verdict"] == "CASE_INVALID"])) if len(gold) > len([v for v in decided if v["verdict"] == "CASE_INVALID"]) else 1.0)}

    def run_gold(self, body: dict, cases: list[dict]) -> list[dict]:
        """Attach engine outcome to each gold case: verdict MATCH or MISMATCH."""
        rec = {"body": body, "version": 1, "status": "PUBLISHED"}
        out = []
        for i, c in enumerate(cases):
            r = engine.evaluate(self.vocab, [rec], body["topic"], c["inputs"], as_of="2026-01-01", with_thresholds=False)
            out.append({"vector_id": c.get("vector_id") or f"G{i:04d}", "origin": "GOLD_MODEL", "inputs": c["inputs"], "expected": c["expected"],
                        "source_span": c.get("source_span"), "verdict": "MATCH" if r["outcome"] == c["expected"] else "MISMATCH"})
        return out

    # ------------------------------------------------------------------ drafts / review / publish
    def list_rules(self, actor: IdentityContext, topic: str | None = None, status: str | None = None) -> dict:
        self.require_author(actor)
        rules = [{"rule_id": r["rule_id"], "version": r["version"], "topic": r["body"]["topic"], "status": r["status"],
                  "label": r["body"]["conclusion"]["label"], "release_id": r["release_id"], "published_at": r["published_at"],
                  "published_by": r["published_by"]} for r in self.store.current_records(("PUBLISHED", "STALE", "RETIRED"))]
        drafts = [{"id": d["id"], "rule_id": d["rule_id"], "topic": d["body"].get("topic"), "origin": d["origin"], "row_version": d["row_version"],
                   "author": d["author_subject_id"], "updated_at": d["updated_at"]} for d in self.store.list_drafts()]
        if topic:
            rules = [r for r in rules if r["topic"] == topic]
            drafts = [d for d in drafts if d["topic"] == topic]
        if status:
            rules = [r for r in rules if r["status"] == status]
        return {"rules": rules, "drafts": drafts, "stale": sum(1 for r in rules if r["status"] == "STALE")}

    def create_draft(self, actor: IdentityContext, body: dict, origin: str = "MANUAL") -> dict:
        self.require_author(actor)
        if origin not in {"MANUAL", "MODEL_CANDIDATE"} or not isinstance(body, dict) or not isinstance(body.get("rule_id"), str):
            raise OpsError(422, "RULE_DRAFT_INVALID", "Bản nháp luật không hợp lệ.")
        draft_id = uuid7()
        now = _iso(self.clock())
        self.store.put_draft(draft_id, body["rule_id"], body, actor.subject_id, origin, now)
        self.store.audit(now, actor.subject_id, "DRAFT_CREATED", body["rule_id"], None, {"draft_id": draft_id, "origin": origin})
        return {"id": draft_id, "row_version": 1}

    def update_draft(self, actor: IdentityContext, draft_id: str, body: dict, row_version: int) -> dict:
        self.require_author(actor)
        draft = self._draft(draft_id)
        if draft["author_subject_id"] != actor.subject_id and not REVIEW_ROLES & self._roles(actor):
            raise OpsError(403, "FORBIDDEN", "Không sửa được bản nháp của người khác.")
        try:
            self.store.update_draft(draft_id, body, row_version, _iso(self.clock()))
        except Conflict:
            raise OpsError(409, "RULE_DRAFT_VERSION_CONFLICT", "Bản nháp đã được sửa ở nơi khác.") from None
        return {"id": draft_id, "row_version": row_version + 1}

    def _draft(self, draft_id: str) -> dict:
        draft = self.store.get_draft(draft_id)
        if draft is None:
            raise OpsError(404, "RULE_DRAFT_NOT_FOUND", "Không có bản nháp này.")
        return draft

    def validate_draft(self, actor: IdentityContext, draft_id: str, gold: list[dict] | None = None) -> dict:
        self.require_author(actor)
        draft = self._draft(draft_id)
        report = self.validate_body(draft["body"])
        vectors = list(report["vectors"])
        if gold and not report["issues"]:
            vectors += self.run_gold(draft["body"], gold)
        nxt = (self.store.latest_version(draft["rule_id"]) or {"version": 0})["version"] + 1
        if not report["issues"]:
            self.store.replace_vectors(draft["rule_id"], nxt, vectors)
        return {"issues": report["issues"], "vector_count": len(report["vectors"]), "mismatches": report["mismatches"],
                "gold": self.gold_report(vectors), "next_version": nxt, "variables": report["variables"]}

    def review(self, actor: IdentityContext, draft_id: str, verdict: str, note: str) -> dict:
        self.require_reviewer(actor)
        if verdict not in {"approved", "rejected", "needs_source"} or len((note or "").strip()) < 8:
            raise OpsError(422, "RULE_REVIEW_INVALID", "Cần phán quyết hợp lệ và ghi chú tối thiểu 8 ký tự.")
        draft = self._draft(draft_id)
        if draft["author_subject_id"] == actor.subject_id and IdentityRole.KNOWLEDGE_ADMIN not in self._roles(actor):
            raise OpsError(403, "FORBIDDEN", "Người soạn không tự duyệt luật của mình.")
        now = _iso(self.clock())
        self.store.add_review(uuid7(), draft_id, actor.subject_id, verdict, note.strip(), now)
        self.store.audit(now, actor.subject_id, "DRAFT_REVIEWED", draft["rule_id"], None, {"draft_id": draft_id, "verdict": verdict})
        return {"draft_id": draft_id, "verdict": verdict}

    def _token(self, preview_id: str, actor: str, payload_hash: str) -> str:
        return hmac.new(self._key, f"{preview_id}|{actor}|{payload_hash}".encode(), hashlib.sha256).hexdigest()

    def _save_preview(self, actor: IdentityContext, kind: str, payload: dict) -> dict:
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        preview_id = uuid7()
        expires = self.clock() + PREVIEW_TTL
        self.store.save_preview(preview_id, actor.subject_id, kind, payload, payload_hash, _iso(expires))
        return {"preview_id": preview_id, "confirmation_token": self._token(preview_id, actor.subject_id, payload_hash), "expires_at": _iso(expires)}

    def publish_preview(self, actor: IdentityContext, draft_id: str) -> dict:
        self.require_reviewer(actor)
        draft = self._draft(draft_id)
        report = self.validate_body(draft["body"])
        if report["issues"]:
            raise OpsError(422, "RULE_VALIDATION_FAILED", "Luật còn lỗi cấu trúc hoặc nguyên văn.")
        if report["mismatches"]:
            raise OpsError(422, "RULE_VECTORS_FAILED", "Bộ máy lệch với kiểm chứng độc lập.")
        nxt = (self.store.latest_version(draft["rule_id"]) or {"version": 0})["version"] + 1
        gold = self.gold_report(self.store.vectors(draft["rule_id"], nxt))
        if gold["total"] and (gold["rate"] < GOLD_MIN_MATCH or gold["mismatch_pending"]):
            raise OpsError(422, "RULE_GOLD_BELOW_THRESHOLD", "Bộ gold chưa đạt hoặc còn ca lệch chưa có phán quyết.")
        reviews = self.store.reviews(draft_id)
        approved = [r for r in reviews if r["verdict"] == "approved"]
        if not approved or reviews[-1]["verdict"] != "approved":
            raise OpsError(409, "RULE_NOT_APPROVED", "Luật chưa được duyệt.")
        sha = canonical_sha256(draft["body"])
        payload = {"draft_id": draft_id, "rule_id": draft["rule_id"], "version": nxt, "content_sha256": sha}
        out = self._save_preview(actor, "PUBLISH", payload)
        return {**out, "change": {"rule_id": draft["rule_id"], "version": nxt, "topic": draft["body"]["topic"], "vectors": len(report["vectors"]),
                "gold": gold, "supersedes_version": nxt - 1 or None}}

    def retire_preview(self, actor: IdentityContext, rule_id: str) -> dict:
        self.require_reviewer(actor)
        latest = self.store.latest_version(rule_id)
        if latest is None or latest["status"] == "RETIRED":
            raise OpsError(404, "RULE_NOT_FOUND", "Không có luật đang dùng với mã này.")
        out = self._save_preview(actor, "RETIRE", {"rule_id": rule_id, "version": latest["version"]})
        return {**out, "change": {"rule_id": rule_id, "version": latest["version"], "retire": True}}

    def confirm(self, actor: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        self.require_reviewer(actor)
        if not idempotency_key or len(idempotency_key) > 200:
            raise OpsError(422, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key.")
        if not token:
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Cần xác nhận.")
        now = _iso(self.clock())
        try:
            taken = self.store.take_preview(preview_id, actor.subject_id, idempotency_key, now,
                lambda payload_hash: hmac.compare_digest(self._token(preview_id, actor.subject_id, payload_hash), token))
        except KeyError:
            raise OpsError(410, "PREVIEW_EXPIRED", "Bản xem trước đã hết hạn hoặc đã dùng.") from None
        except PermissionError:
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Mã xác nhận không đúng.") from None
        if taken[0] == "replay":
            return {**taken[1], "replayed": True}
        _, kind, payload = taken
        if kind == "PUBLISH":
            draft = self._draft(payload["draft_id"])
            if canonical_sha256(draft["body"]) != payload["content_sha256"]:
                raise OpsError(409, "RULE_DRAFT_CHANGED", "Bản nháp đã đổi sau khi xem trước.")
            result = self._publish(draft["body"], actor.subject_id, now)
        else:
            self.store.set_status(payload["rule_id"], payload["version"], "RETIRED", now)
            self.store.audit(now, actor.subject_id, "RULE_RETIRED", payload["rule_id"], payload["version"])
            result = {"rule_id": payload["rule_id"], "version": payload["version"], "status": "RETIRED"}
        self.store.remember(idempotency_key, actor.subject_id, result)
        return {**result, "replayed": False}

    def _publish(self, body: dict, by: str, now: str, graph_version: str = "none") -> dict:
        latest = self.store.latest_version(body["rule_id"])
        version = (latest["version"] if latest else 0) + 1
        stored = {**body, "version": version}
        rel = self.release()
        self.store.add_version(body["rule_id"], version, stored, canonical_sha256(stored), graph_version, rel["release_id"], rel["binding_sha256"],
            "PUBLISHED", by, now, source_hashes(stored, self.text_of_unit))
        if latest and latest["status"] in {"PUBLISHED", "STALE"}:
            self.store.set_status(latest["rule_id"], latest["version"], "RETIRED", now)
        self.store.audit(now, by, "RULE_PUBLISHED", body["rule_id"], version, {"release_id": rel["release_id"]})
        return {"rule_id": body["rule_id"], "version": version, "status": "PUBLISHED"}

    def vectors(self, actor: IdentityContext, rule_id: str, version: int) -> dict:
        self.require_reviewer(actor)
        vectors = self.store.vectors(rule_id, version)
        return {"rule_id": rule_id, "version": version, "vectors": vectors, "gold": self.gold_report(vectors)}

    # ------------------------------------------------------------------ seed + staleness
    def seed_from_directory(self, rules_dir: Path, gold_dir: Path | None = None, *, actor: str = "repo-config") -> dict:
        """Publish config rules that passed the same checks as a manual draft. Idempotent; a changed file becomes version + 1."""
        published, skipped, failed = [], [], []
        for path in sorted(Path(rules_dir).glob("*.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
            latest = self.store.latest_version(body["rule_id"])
            if latest and latest["content_sha256"] == canonical_sha256({**body, "version": latest["version"]}) and latest["status"] != "STALE":
                skipped.append(body["rule_id"])
                continue
            report = self.validate_body(body)
            if report["issues"] or report["mismatches"]:
                failed.append({"rule_id": body["rule_id"], "issues": report["issues"], "mismatches": report["mismatches"][:3]})
                continue
            vectors = list(report["vectors"])
            gold_file = Path(gold_dir) / path.name if gold_dir else None
            if gold_file and gold_file.is_file():
                vectors += self.run_gold(body, json.loads(gold_file.read_text(encoding="utf-8"))["cases"])
            nxt = (latest["version"] if latest else 0) + 1
            gold = self.gold_report(vectors)
            if gold["total"] and (gold["rate"] < GOLD_MIN_MATCH or gold["mismatch_pending"]):
                failed.append({"rule_id": body["rule_id"], "gold": gold})
                continue
            self.store.replace_vectors(body["rule_id"], nxt, vectors)
            published.append(self._publish(body, actor, _iso(self.clock())))
        return {"published": published, "skipped": skipped, "failed": failed}

    def check_staleness(self) -> list[dict]:
        """Mark PUBLISHED rules STALE when any cited unit's text changed or vanished."""
        stale = []
        now = _iso(self.clock())
        for rec in self.store.current_records(("PUBLISHED",)):
            current = source_hashes(rec["body"], self.text_of_unit)
            changed = [u for u, h in rec["source_hashes"].items() if current.get(u) != h]
            if changed:
                self.store.set_status(rec["rule_id"], rec["version"], "STALE", now)
                self.store.audit(now, "system", "RULE_STALE", rec["rule_id"], rec["version"], {"units": changed})
                stale.append({"rule_id": rec["rule_id"], "version": rec["version"], "units": changed})
        return stale

    def summary(self) -> dict:
        recs = self.store.current_records(("PUBLISHED", "STALE", "RETIRED"))
        return {"active": sum(1 for r in recs if r["status"] == "PUBLISHED"), "stale": sum(1 for r in recs if r["status"] == "STALE")}


def _walk_preds(node: dict):
    from campus247.domain.policy_rules.rule import predicates
    return predicates(node)
