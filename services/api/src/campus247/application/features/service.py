"""Feature service (F0.3): resolves the effective value of every feature and runs the preview -> confirm change flow.

Priority (highest first): emergency off, unexpired admin override matching the audience, legacy environment variable,
profile file, registry default. Dependencies, startup wiring and system capabilities then narrow the result.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from campus247.features.registry import BY_KEY, FEATURES, FeatureDefinition, feature_for_path, validate_registry
from campus247.ports.campus_ops import OpsError, uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

ADMIN_ROLES = {IdentityRole.SYSTEM_ADMIN, IdentityRole.KNOWLEDGE_ADMIN}
CACHE_SECONDS = 2.0
PREVIEW_TTL = timedelta(minutes=10)
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
TRUE_WORDS, FALSE_WORDS = {"1", "true", "on", "yes"}, {"0", "false", "off", "no", ""}


def parse_bool(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return raw
    word = str(raw).strip().lower()
    return True if word in TRUE_WORDS else False if word in FALSE_WORDS else None


@dataclass(frozen=True)
class FeatureExplanation:
    key: str
    enabled: bool
    reasons: tuple[str, ...]
    source: str


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


class FeatureService:
    def __init__(self, *, store=None, profile_values: dict[str, Any] | None = None, env: dict[str, str] | None = None,
                 capabilities: Callable[[], dict[str, bool]] | None = None, wired: frozenset[str] | None = None,
                 clock: Callable[[], datetime] | None = None, monotonic: Callable[[], float] = time.monotonic,
                 signing_key: str = "feature-flags-local", profile: str = "local", features=FEATURES):
        problems = validate_registry(features)
        if problems:
            raise ValueError("feature registry invalid: " + "; ".join(problems))
        self.features = {f.key: f for f in features}
        self.store, self.profile, self._key = store, profile, signing_key.encode()
        self.env = dict(env or {})
        self.profile_values = dict(profile_values or {})
        unknown = sorted(set(self.profile_values) - set(self.features))
        if unknown:
            raise ValueError("unknown feature key in profile file: " + ", ".join(unknown))
        off = {x.strip() for x in self.env.get("CAMPUS247_FEATURES_OFF", "").split(",") if x.strip()}
        self.emergency_all, self.emergency = "*" in off, off - {"*"}
        self.capabilities = capabilities
        self.wired = wired  # None = every startup_wired feature counts as wired
        self.clock, self._mono = clock or (lambda: datetime.now(timezone.utc)), monotonic
        self._cache: tuple[int, dict[str, dict]] = (0, {})
        self._cache_at = -1e9
        self.store_error = False
        # dependents for the admin view
        self.dependents: dict[str, list[str]] = {k: [] for k in self.features}
        for f in features:
            for dep in f.depends_on:
                self.dependents[dep].append(f.key)

    # ------------------------------------------------------------ overrides cache
    def _overrides(self) -> tuple[int, dict[str, dict]]:
        if self.store is None:
            return 0, {}
        now = self._mono()
        if now - self._cache_at < CACHE_SECONDS:
            return self._cache
        try:
            version = self.store.version()
            if version != self._cache[0] or self._cache_at < 0:
                self._cache = self.store.overrides()
            self.store_error = False
        except Exception:  # noqa: BLE001 -- keep the last good snapshot, report through store_error
            self.store_error = True
        self._cache_at = now
        return self._cache

    def version(self) -> int:
        return self._overrides()[0]

    # ------------------------------------------------------------ resolution
    @staticmethod
    def _percent(key: str, subject: str) -> int:
        return int(hashlib.sha256(f"{key}:{subject}".encode()).hexdigest()[:8], 16) % 100

    def _audience_ok(self, f: FeatureDefinition, audience: dict, actor: IdentityContext | None) -> bool:
        if not audience:
            return True
        if f.kind in {"job", "ops"}:
            return True
        roles = set(audience.get("roles") or [])
        if roles:
            have = {r.value for r in actor.roles} if actor else {"GUEST"}
            if not roles & have:
                return False
        subjects = audience.get("subjects")
        if subjects and (actor is None or actor.subject_id not in subjects):
            return False
        percent = audience.get("percent")
        if percent is not None and (actor is None or self._percent(f.key, actor.subject_id) >= int(percent)):
            return False
        return True

    def _configured(self, f: FeatureDefinition, actor: IdentityContext | None, overrides: dict[str, dict]) -> tuple[Any, str, bool]:
        """(value, source, audience_excluded)."""
        if f.locked:
            return True, "locked", False
        if self.emergency_all or f.key in self.emergency:
            return False, "emergency_off", False
        ov = overrides.get(f.key)
        excluded = False
        if ov and not (ov["expires_at"] and ov["expires_at"] <= _iso(self.clock())):
            if self._audience_ok(f, ov["audience"], actor):
                return self._coerce(f, ov["value"]), "override", False
            excluded = True
        if f.env_alias and f.env_alias in self.env:
            parsed = self._env_value(f, self.env[f.env_alias])
            if parsed is not None:
                return parsed, "env", excluded
        if f.key in self.profile_values:
            return self._coerce(f, self.profile_values[f.key]), "profile", excluded
        return self._default(f), "default", excluded

    @staticmethod
    def _default(f: FeatureDefinition) -> Any:
        return f.default_value if f.variants else f.default

    @staticmethod
    def _coerce(f: FeatureDefinition, raw: Any) -> Any:
        if f.variants:
            word = str(raw).strip().lower()
            return word if word in f.variants else f.default_value
        parsed = parse_bool(raw)
        return f.default if parsed is None else parsed

    @staticmethod
    def _env_value(f: FeatureDefinition, raw: str) -> Any:
        if f.variants:
            word = raw.strip().lower()
            return word if word in f.variants else None
        if f.key in {"identity.oidc"}:
            return bool(raw.strip())
        return parse_bool(raw)

    def explain(self, key: str, actor: IdentityContext | None = None, *, _overrides=None, _depth=0) -> FeatureExplanation:
        f = self.features[key]
        overrides = _overrides if _overrides is not None else self._overrides()[1]
        value, source, excluded = self._configured(f, actor, overrides)
        reasons: list[str] = []
        configured_on = (value != f.variants[0]) if f.variants else bool(value)
        if not configured_on:
            reasons.append("EMERGENCY_OFF" if source == "emergency_off" else "AUDIENCE_EXCLUDED" if excluded else "CONFIGURED_OFF")
        elif not f.locked:
            for dep in f.depends_on:
                if _depth < 12 and not self.explain(dep, actor, _overrides=overrides, _depth=_depth + 1).enabled:
                    reasons.append(f"DEPENDENCY_OFF:{dep}")
            if f.startup_wired and self.wired is not None and key not in self.wired:
                reasons.append("NOT_WIRED_RESTART_REQUIRED")
            if f.capability and f.capability_scope == "all" and self.capabilities is not None and self.capabilities().get(f.capability) is False:
                reasons.append("SYSTEM_STATE:" + f.capability)
        enabled = not reasons
        return FeatureExplanation(key, enabled, tuple(reasons), source)

    def enabled(self, key: str, actor: IdentityContext | None = None) -> bool:
        if key not in self.features:
            raise KeyError(key)
        return self.explain(key, actor).enabled

    def value(self, key: str, actor: IdentityContext | None = None) -> Any:
        f = self.features[key]
        if not f.variants:
            return self.enabled(key, actor)
        exp = self.explain(key, actor)
        if not exp.enabled:
            return f.variants[0]
        return self._configured(f, actor, self._overrides()[1])[0]

    def snapshot(self, actor: IdentityContext | None = None, *, client_only: bool = False) -> dict[str, Any]:
        version, overrides = self._overrides()
        values = {}
        for k, f in self.features.items():
            if client_only and not f.client_visible:
                continue
            if f.variants:
                exp = self.explain(k, actor, _overrides=overrides)
                values[k] = self._configured(f, actor, overrides)[0] if exp.enabled else f.variants[0]
            else:
                values[k] = self.explain(k, actor, _overrides=overrides).enabled
        return {"version": version, "features": values}

    def feature_for_path(self, path: str, method: str = "GET") -> str | None:
        key = feature_for_path(path)
        if key is None:
            return None
        f = self.features[key]
        if f.capability_scope == "write" and f.capability and method.upper() not in WRITE_METHODS:
            return key  # reads still gated by the config; only the capability part is write-only (handled in explain)
        return key

    def gate(self, path: str, method: str, actor: IdentityContext | None) -> str | None:
        """Key of the disabled feature that owns this request, or None when the request may proceed."""
        key = feature_for_path(path)
        if key is None:
            return None
        f = self.features[key]
        exp = self.explain(key, actor)
        if exp.enabled:
            if f.capability and f.capability_scope == "write" and method.upper() in WRITE_METHODS and self.capabilities is not None:
                if self.capabilities().get(f.capability) is False:
                    return key
            return None
        # capability reasons never block reads
        return key

    def tool_enabled(self, tool_id: str, actor: IdentityContext | None = None) -> bool:
        owner = next((f.key for f in self.features.values() if tool_id in f.tools), None)
        return True if owner is None else self.enabled(owner, actor)

    SUPERSEDED_BY = {"exam_reminders": "proactive.nudges"}  # the old exam reminder stops when its replacement is on, so nobody is nudged twice

    def job_enabled(self, job: str) -> bool:
        owner = next((f.key for f in self.features.values() if job in f.jobs), None)
        if job in self.SUPERSEDED_BY and self.enabled(self.SUPERSEDED_BY[job]):
            return False
        return True if owner is None else self.enabled(owner)

    # ------------------------------------------------------------ admin view
    def admin_items(self) -> dict[str, Any]:
        version, overrides = self._overrides()
        items = []
        for f in self.features.values():
            value, source, _ = self._configured(f, None, overrides)
            exp = self.explain(f.key, None, _overrides=overrides)
            ov = overrides.get(f.key)
            sources = {"default": self._default(f), "profile": self.profile_values.get(f.key),
                       "env": self.env.get(f.env_alias) if f.env_alias else None, "override": ov["value"] if ov else None,
                       "emergency_off": f.key in self.emergency or self.emergency_all}
            items.append({
                "key": f.key, "title": f.title, "area": f.area, "kind": f.kind, "locked": f.locked, "startup_wired": f.startup_wired,
                "variants": list(f.variants), "depends_on": list(f.depends_on), "dependents": self.dependents[f.key],
                "configured": {"value": value, "source": source, **({"expires_at": ov["expires_at"], "reason": ov["reason"], "by": ov["by"], "at": ov["at"],
                                                                      "audience": ov["audience"]} if ov and source == "override" else {})},
                "sources": sources, "effective_for_all": exp.enabled, "off_reasons": list(exp.reasons),
                "entry_points": {"api": list(f.api_prefixes) + list(f.api_patterns), "pages": list(f.pages), "jobs": list(f.jobs), "tools": list(f.tools)},
                "cost": f.cost})
        return {"version": version, "profile": self.profile, "store_error": self.store_error, "items": items}

    def summary(self) -> dict[str, Any]:
        """Counts for the operations page: features off, admin overrides in force, features waiting for a restart."""
        data = self.admin_items()
        items = data["items"]
        return {"off": sum(1 for i in items if not i["effective_for_all"]), "overrides": sum(1 for i in items if i["configured"]["source"] == "override"),
                "restart_required": sum(1 for i in items if "NOT_WIRED_RESTART_REQUIRED" in i["off_reasons"]), "store_error": data["store_error"]}

    # ------------------------------------------------------------ change flow
    @staticmethod
    def require_admin(actor: IdentityContext) -> None:
        if not ADMIN_ROLES.intersection(actor.roles):
            raise OpsError(403, "FORBIDDEN", "Chỉ quản trị viên mới đổi được cờ tính năng.")

    def _token(self, preview_id: str, actor: str, payload_hash: str) -> str:
        return hmac.new(self._key, f"{preview_id}|{actor}|{payload_hash}".encode(), hashlib.sha256).hexdigest()

    def preview_change(self, actor: IdentityContext, key: str, *, value: Any = None, audience: dict | None = None,
                       expires_at: str | None = None, reason: str = "", expected_version: int, remove: bool = False) -> dict:
        self.require_admin(actor)
        f = self.features.get(key)
        if f is None:
            raise OpsError(404, "FEATURE_UNKNOWN", "Không có tính năng này.")
        if f.locked:
            raise OpsError(422, "FEATURE_LOCKED", "Tính năng lõi không được tắt.")
        reason = (reason or "").strip()
        if len(reason) < 10 or len(reason) > 300:
            raise OpsError(422, "FEATURE_VALUE_INVALID", "Lý do phải từ 10 đến 300 ký tự.")
        audience = audience or {}
        if not isinstance(audience, dict) or set(audience) - {"roles", "subjects", "percent"} or len(audience.get("subjects") or []) > 200:
            raise OpsError(422, "FEATURE_VALUE_INVALID", "Đối tượng không hợp lệ.")
        if "percent" in audience and not (isinstance(audience["percent"], int) and 0 <= audience["percent"] <= 100):
            raise OpsError(422, "FEATURE_VALUE_INVALID", "Tỷ lệ phải là số nguyên 0-100.")
        if audience and f.kind in {"job", "ops"}:
            raise OpsError(422, "FEATURE_VALUE_INVALID", "Việc nền không áp dụng theo đối tượng.")
        if not remove:
            if f.variants:
                value = str(value).lower()
                if value not in f.variants:
                    raise OpsError(422, "FEATURE_VALUE_INVALID", "Giá trị ngoài danh sách cho phép.")
            else:
                if not isinstance(value, bool):
                    raise OpsError(422, "FEATURE_VALUE_INVALID", "Giá trị phải là bật hoặc tắt.")
            if expires_at:
                try:
                    exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                except ValueError:
                    raise OpsError(422, "FEATURE_VALUE_INVALID", "Hạn không hợp lệ.") from None
                if exp <= self.clock():
                    raise OpsError(422, "FEATURE_VALUE_INVALID", "Hạn đã qua.")
                expires_at = _iso(exp)
            turning_on = value is True or (f.variants and value != f.variants[0])
            if turning_on:
                for dep in f.depends_on:
                    if not self.enabled(dep):
                        raise OpsError(409, "FEATURE_DEPENDENCY_OFF", f"Cần bật '{dep}' trước.")
        version = self.version()
        if expected_version != version:
            raise OpsError(409, "FEATURE_VERSION_CONFLICT", f"Phiên bản cờ đã đổi (hiện tại {version}).")
        payload = {"key": key, "value": None if remove else value, "audience": {} if remove else audience,
                   "expires_at": None if remove else expires_at, "reason": reason, "remove": bool(remove)}
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        preview_id = uuid7()
        expires = self.clock() + PREVIEW_TTL
        self.store.save_preview(preview_id, actor.subject_id, payload, payload_hash, version, _iso(expires))
        current = self.explain(key).enabled if not f.variants else self.value(key)
        to_off = (not remove) and (value is False or (f.variants and value == f.variants[0]))
        impact = {"also_off": self._cascade(key) if to_off else [], "api_prefixes": list(f.api_prefixes), "pages": list(f.pages),
                  "jobs": list(f.jobs), "restart_required": bool(f.startup_wired and not remove and value is True), "data_kept": True}
        return {"preview_id": preview_id, "confirmation_token": self._token(preview_id, actor.subject_id, payload_hash), "expires_at": _iso(expires),
                "change": {"key": key, "from": current, "to": None if remove else value, "remove": bool(remove)}, "impact": impact}

    def _cascade(self, key: str) -> list[str]:
        out, stack = [], list(self.dependents[key])
        while stack:
            k = stack.pop()
            if k not in out:
                out.append(k)
                stack.extend(self.dependents[k])
        return sorted(k for k in out if self.enabled(k))

    def confirm_change(self, actor: IdentityContext, preview_id: str, token: str, idempotency_key: str) -> dict:
        self.require_admin(actor)
        if not idempotency_key or len(idempotency_key) > 200:
            raise OpsError(422, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key.")
        if not token:
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Cần xác nhận.")
        try:
            receipt = self.store.apply(preview_id=preview_id, actor=actor.subject_id, idempotency_key=idempotency_key, now=_iso(self.clock()),
                                       token_check=lambda payload_hash: hmac.compare_digest(self._token(preview_id, actor.subject_id, payload_hash), token))
        except KeyError:
            raise OpsError(410, "PREVIEW_EXPIRED", "Bản xem trước đã hết hạn hoặc đã dùng.") from None
        except PermissionError:
            raise OpsError(428, "CONFIRMATION_REQUIRED", "Mã xác nhận không đúng.") from None
        except ValueError as error:
            raise OpsError(409, "FEATURE_VERSION_CONFLICT", "Phiên bản cờ đã đổi: " + str(error).split(":")[-1]) from None
        self._cache_at = -1e9  # this process sees its own change immediately
        return receipt

    def audit(self, actor: IdentityContext, key: str | None, cursor: int | None, limit: int = 50) -> dict:
        self.require_admin(actor)
        rows = self.store.audit(key, cursor, max(1, min(limit, 200)))
        return {"items": rows, "next_cursor": rows[-1]["id"] if len(rows) == limit else None}
