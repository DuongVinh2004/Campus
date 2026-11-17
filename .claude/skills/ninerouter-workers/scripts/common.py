"""Shared config and policy for 9router (Antigravity) workers.

Policy lives here, in code, so a worker can never talk its way past it.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO = SKILL_DIR.parents[2]
ENV_FILE = REPO / ".env"
RUNS_DIR = Path.home() / ".claude" / "ninerouter-runs"
DEFAULT_MODEL = "ag/gemini-3.8-flash-high"
DEFAULT_BASE_URL = "http://127.0.0.1:20128/v1"

# Paths a worker may NEVER write, whatever --allow says: core logic, data, secrets, config.
HARD_DENY = [
    ".env", ".env.*", "**/.env", "**/.env.*",
    ".git/**", "**/node_modules/**", ".tooling/**", ".claude/**", ".github/**",
    "AGENTS.md", "CLAUDE.md", "**/AGENTS.md", "**/CLAUDE.md",
    "data/**", "archive/**", "release/**", "downloads/**", "**/evidence/**", "**/backups/**",
    "**/*.sqlite", "**/*.sqlite3", "**/*.db", "**/*.dump", "**/*.pem", "**/*.key",
    "contracts/**", "infra/**", "compose.yaml", "docs/00-governance/**",
    "services/api/migrations/**", "services/api/alembic.ini", "**/migrations/**", "**/alembic/**",
    # backend: everything except tests is core logic
    "services/api/src/**", "workers/**", "packages/**/src/**",
    # web: API clients, auth, server routes, middleware
    "apps/web/src/lib/**", "apps/web/src/app/api/**", "apps/web/src/middleware.ts", "apps/web/next.config.*",
    # dependency manifests and lockfiles
    "package.json", "**/package.json", "pnpm-lock.yaml", "**/package-lock.json", "pnpm-workspace.yaml",
    "pyproject.toml", "**/pyproject.toml", "uv.lock", "**/uv.lock",
    # eval gold / datasets are data
    "evals/**/gold/**", "evals/**/datasets/**", "evals/**/*.jsonl",
]

# Context files that must never be sent out (data leaves the machine via Antigravity).
NEVER_SEND = [
    ".env", ".env.*", "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.sqlite", "**/*.sqlite3",
    "**/*.db", "**/*.dump", "data/**", "**/backups/**", "**/evidence/**", ".tooling/**", "**/*credential*",
    "**/secrets/**",
]

SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9-]{16,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:(?:api[_-]?key|secret|password|passwd|token)\s*[=:]\s*['\"][^'\"\s]{8,}['\"])"
)

# Added lines matching these block a patch (destructive / out-of-scope behaviour).
DANGER_PATTERNS = [
    (r"\brm\s+-[a-zA-Z]*[rf]", "shell rm -rf"),
    (r"\bRemove-Item\b", "PowerShell Remove-Item"),
    (r"shutil\.rmtree|os\.remove\(|os\.unlink\(|\.unlink\(|os\.rmdir\(", "file deletion (python)"),
    (r"\bfs\.(rm|rmSync|unlink|unlinkSync|rmdir|rmdirSync)\b", "file deletion (node)"),
    (r"(?i)\b(drop\s+(table|database|schema)|truncate\s+table|delete\s+from)\b", "destructive SQL"),
    (r"\bgit\s+(push|reset|clean|rebase|checkout\s+--|branch\s+-D|filter-branch)", "git history/working-tree command"),
    (r"\bsubprocess\.|child_process|\bexecSync\(|\bspawn\(|\bos\.system\(", "process execution"),
    (r"(?<![\w.])eval\(|new Function\(", "dynamic code execution"),
    (r"dangerouslySetInnerHTML", "raw HTML injection"),
    (r"localStorage\.clear\(|indexedDB\.deleteDatabase", "client data wipe"),
    (r"https?://(?!localhost|127\.0\.0\.1|example\.(com|org)|www\.w3\.org)[a-z0-9.-]+\.[a-z]{2,}", "external URL"),
    (r"(?i)(TODO|rest of (the )?(file|code)|existing code|unchanged)\s*(\.\.\.|…)|^\s*(//|#|/\*)\s*(\.\.\.|…)\s*$", "truncated output placeholder"),
    (r"<REDACTED>", "redaction placeholder (would overwrite a real secret)"),
    (r"^\s{0,6}\d{1,5}\| ", "context line-number prefix copied into code"),
    (r"\b(fetch|axios)\s*[.(]|new WebSocket\(|navigator\.sendBeacon", "network call (API logic belongs to the supervisor)"),
]
# Findings that are reported but do not block apply.
WARN_ONLY = {"external URL", "network call (API logic belongs to the supervisor)"}
DANGER_RE = [(re.compile(p, re.MULTILINE), why) for p, why in DANGER_PATTERNS]


def norm(rel: str) -> str:
    rel = rel.strip().strip("`\"'").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def match_any(rel: str, globs: list[str]) -> bool:
    # Windows paths are case-insensitive: compare lower-case so "SERVICES/Api/..." cannot dodge a deny rule.
    rel = norm(rel).lower()
    for g in globs:
        g = norm(g).lower()
        if fnmatch.fnmatchcase(rel, g):
            return True
        if g.startswith("**/") and fnmatch.fnmatchcase(rel, g[3:]):
            return True
        if g.endswith("/**") and (rel == g[:-3] or rel.startswith(g[:-2])):
            return True
    return False


def safe_rel(rel: str) -> str | None:
    """Return a normalized repo-relative path, or None if it escapes the repo."""
    rel = norm(rel)
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        return None
    parts = rel.split("/")
    # Reject Windows aliasing tricks: "AGENTS.md." / "x " (trailing dot/space are stripped by Windows),
    # alternate data streams ("a:b"), 8.3 short names ("PROGRA~1"), control chars, empty segments.
    for seg in parts:
        if seg in ("", ".", "..") or seg[-1] in ". " or ":" in seg or re.search(r"~\d", seg) or re.search(r"[\x00-\x1f<>|?*\"]", seg):
            return None
    target = (REPO / rel).resolve()
    try:
        real_rel = target.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return None
    # A symlink/junction inside the repo may point at a denied place: callers check both names.
    return rel if real_rel.lower() == rel.lower() else f"{rel}\0{real_rel}"


def deny_hit(rel: str, globs: list[str]) -> bool:
    """True if the path or what it really resolves to matches globs."""
    return any(match_any(p, globs) for p in rel.split("\0"))


def load_config() -> dict[str, str]:
    cfg = {"NINEROUTER_BASE_URL": DEFAULT_BASE_URL, "NINEROUTER_MODEL": DEFAULT_MODEL}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("NINEROUTER_") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    if not cfg.get("NINEROUTER_API_KEY"):
        raise SystemExit("NINEROUTER_API_KEY missing in repo .env")
    return cfg


def redact(text: str) -> tuple[str, int]:
    return SECRET_RE.subn("<REDACTED>", text)
