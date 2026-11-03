"""Offline dependency gate: approved names, exact pins, closure and artifact hashes.

References in a virtual root are not resolved package records. Unknown direct
or transitive packages remain denied; resolving a graph does not approve it.
"""
import sys
import re
import hashlib
from pathlib import Path
import tomllib
from urllib.parse import unquote, urlsplit

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)*(?:\.post[0-9]+)?")
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([A-Za-z0-9_,.-]+)\])?==([0-9]+(?:\.[0-9]+)*(?:\.post[0-9]+)?)(?:\s*;\s*(.+))?")
OTEL_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([A-Za-z0-9_,.-]+)\])?==(0\.66b0)(?:\s*;\s*(.+))?")
REGISTRY = "https://pypi.org/simple"
RUNTIME = ">=3.12,<3.14"
# Owner approval on 2026-11-03 covers these exact candidate bytes and the
# reviewed 133 unlisted package/version additions. New names/versions still
# require new approval.
APPROVAL_REFERENCE = "DIRECT-HUMAN-2026-11-03-STACK-002"
APPROVED_CANDIDATE_SHA256 = "251e0a8fbd1f5910abd30105a3a0e6b63f6ab9a51244d209cfc29848b2dbce46"
APPROVED_ADDITIONAL_PACKAGE_COUNT = 133
# Explicit human approval on 2026-10-05 for only these prereleases within the
# hash-bound candidate. A name allowlist alone never enables this exception.
APPROVED_OTEL_PRERELEASES = frozenset((name, "0.66b0") for name in (
    "opentelemetry-exporter-http-transport",
    "opentelemetry-exporter-otlp-common",
    "opentelemetry-instrumentation",
    "opentelemetry-instrumentation-asgi",
    "opentelemetry-instrumentation-fastapi",
    "opentelemetry-instrumentation-httpx",
    "opentelemetry-instrumentation-redis",
    "opentelemetry-instrumentation-sqlalchemy",
    "opentelemetry-semantic-conventions",
    "opentelemetry-util-http",
))


def normalize_package_name(raw_spec: str) -> str:
    # Extracts package name before [extras] or >= / == version specs
    match = re.match(r"^([a-zA-Z0-9_\-\.]+)", raw_spec.strip())
    if match:
        return match.group(1).lower().replace("_", "-")
    return raw_spec.strip().lower()


def approved_names(document: str) -> set[str]:
    header = document.split("---", 2)
    if len(header) < 3 or not re.search(r'^status:\s*"approved"\s*$', header[1], re.MULTILINE):
        raise ValueError("approved dependency policy required")
    section = document.split("## 2. Python Backend & Worker Allowlist", 1)[1].split("## 3.", 1)[0]
    names = set(re.findall(r"^\| `([a-z0-9-]+)` \|", section, re.MULTILINE))
    if not names:
        raise ValueError("dependency allowlist missing")
    return names


def _requirements(values, errors, approved_versions=()) -> dict[str, dict]:
    result = {}
    if not isinstance(values, list) or not values:
        errors.append("non-empty dependency declarations required")
        return result
    for value in values:
        match = PIN.fullmatch(value) if isinstance(value, str) else None
        if match is None and isinstance(value, str):
            candidate = OTEL_PIN.fullmatch(value)
            if candidate is not None:
                pair = (normalize_package_name(candidate[1]), candidate[3])
                if pair in APPROVED_OTEL_PRERELEASES and pair in approved_versions:
                    match = candidate
        if match is None:
            errors.append("dependency must use an exact stable == pin; URL/VCS/range/wildcard denied")
            continue
        name, extras, version, marker = match.groups()
        name = normalize_package_name(name)
        if name in result:
            errors.append("duplicate direct dependency")
        item = {"name": name, "specifier": "==" + version}
        if extras:
            item["extras"] = sorted(normalize_package_name(extra) for extra in extras.split(","))
        if marker:
            item["marker"] = marker
        result[name] = item
    return result


def _metadata(values):
    if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
        return None
    result = {}
    for value in values:
        name = value.get("name")
        if not isinstance(name, str) or NAME.fullmatch(name) is None or name in result:
            return None
        result[name] = value
    return result


def _artifact(artifact, name, version, *, wheel=False) -> bool:
    if not isinstance(artifact, dict):
        return False
    try:
        url = urlsplit(artifact.get("url", ""))
        valid_url = (url.scheme == "https" and url.hostname == "files.pythonhosted.org"
                     and url.port is None and url.username is None and url.password is None
                     and not url.query and not url.fragment and url.path.startswith("/packages/")
                     and (not wheel or url.path.endswith(".whl")))
    except (ValueError, TypeError):
        return False
    filename = unquote(url.path.rsplit("/", 1)[-1])
    if wheel:
        parts = filename.split("-")
        identity_matches = (len(parts) in (5, 6) and normalize_package_name(parts[0]) == name
                            and parts[1] == version)
    else:
        identity_matches = any(filename.lower() == f"{prefix}-{version}{suffix}".lower()
                               for prefix in (name, name.replace("-", "_")) for suffix in (".tar.gz", ".zip"))
    checksum = artifact.get("hash")
    return (valid_url and identity_matches and isinstance(checksum, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", checksum) is not None
            and checksum != "sha256:" + "0" * 64
            and type(artifact.get("size")) is int and artifact["size"] > 0)


def validate_documents(project: dict, lock: dict, approved: set[str], *, approved_versions=None) -> list[str]:
    """Pure validation for deterministic synthetic tests; never install or connect."""
    errors = []
    approved_versions = approved_versions or set()
    config = project.get("project", {})
    if config.get("requires-python", "").replace(" ", "") != RUNTIME:
        errors.append("project runtime must remain >=3.12,<3.14")
    if lock.get("requires-python", "").replace(" ", "") != RUNTIME:
        errors.append("lock runtime differs from approved project runtime")
    if type(lock.get("version")) is not int or lock["version"] != 1:
        errors.append("unsupported lock format")
    if type(lock.get("revision")) is not int or lock["revision"] < 1:
        errors.append("lock revision required")
    source_options = {"sources", "index", "default-index", "index-url", "extra-index-url", "find-links",
                      "override-dependencies", "constraint-dependencies"}
    if source_options.intersection(project.get("tool", {}).get("uv", {})):
        errors.append("project source overrides require separate approval")
    groups = project.get("dependency-groups", {})
    if set(groups) != {"dev"}:
        errors.append("unreviewed dependency group")
    production = _requirements(config.get("dependencies"), errors, approved_versions)
    development = _requirements(groups.get("dev"), errors, approved_versions)
    declared = production | development
    if len(declared) != len(production) + len(development):
        errors.append("overlapping dependency declarations")
    records = lock.get("package")
    if not isinstance(records, list) or not records or any(not isinstance(p, dict) for p in records):
        return sorted(set(errors + ["resolved package records required"]))
    resolved = {}
    for package in records:
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or NAME.fullmatch(name) is None:
            errors.append("invalid resolved package name")
            continue
        if name in resolved:
            errors.append("duplicate or ambiguous resolved package: " + name)
        resolved[name] = package
        prerelease_approved = (isinstance(version, str)
                              and (name, version) in APPROVED_OTEL_PRERELEASES
                              and (name, version) in approved_versions)
        if not isinstance(version, str) or (VERSION.fullmatch(version) is None and not prerelease_approved):
            errors.append("immutable stable version required: " + name)
        if name == config.get("name"):
            continue
        if name not in approved and (name, version) not in approved_versions:
            errors.append("unapproved resolved dependency: " + name)
        if package.get("source") != {"registry": REGISTRY}:
            errors.append("unapproved registry/VCS/path source: " + name)
        wheels = package.get("wheels")
        if not isinstance(wheels, list) or not wheels or any(not _artifact(a, name, version, wheel=True) for a in wheels):
            errors.append("hashed approved wheel records required: " + name)
        if "sdist" in package and not _artifact(package["sdist"], name, version):
            errors.append("invalid sdist source/hash: " + name)
    root = resolved.get(config.get("name"))
    if root is None or root.get("source") != {"virtual": "."} or root.get("version") != config.get("version"):
        return sorted(set(errors + ["matching virtual root required"]))
    metadata = root.get("metadata", {})
    if _metadata(metadata.get("requires-dist")) != production:
        errors.append("lock drift: production requirement metadata differs")
    if _metadata(metadata.get("requires-dev", {}).get("dev")) != development:
        errors.append("lock drift: dev requirement metadata differs")
    if set(root.get("dev-dependencies", {})) != {"dev"} or set(metadata.get("requires-dev", {})) != {"dev"}:
        errors.append("lock drift: dev groups differ")
    for name, item in declared.items():
        if name not in approved and (name, item["specifier"][2:]) not in approved_versions:
            errors.append("unapproved declared dependency: " + name)
        if name not in resolved:
            errors.append("unresolved declared dependency: " + name)
        elif resolved[name].get("version") != item["specifier"][2:]:
            errors.append("lock drift: exact version differs: " + name)
    edges = {}
    for name, package in resolved.items():
        references = list(package.get("dependencies", []))
        for values in package.get("optional-dependencies", {}).values():
            references.extend(values)
        if name == config.get("name"):
            references.extend(root.get("dev-dependencies", {}).get("dev", []))
            for refs, expected in ((root.get("dependencies", []), production),
                                   (root.get("dev-dependencies", {}).get("dev", []), development)):
                if _metadata(refs) is None or set(_metadata(refs)) != set(expected):
                    errors.append("lock drift: root dependency references differ")
                else:
                    for reference in refs:
                        if reference.get("extra", []) != expected[reference["name"]].get("extras", []):
                            errors.append("lock drift: requested extras differ")
        edges[name] = set()
        for reference in references:
            if not isinstance(reference, dict) or reference.get("name") not in resolved:
                errors.append("unresolved dependency edge: " + name)
                continue
            target = reference["name"]
            edges[name].add(target)
            if "version" in reference and reference["version"] != resolved[target].get("version"):
                errors.append("dependency edge version mismatch: " + name)
            for extra in reference.get("extra", []):
                if extra not in resolved[target].get("optional-dependencies", {}):
                    errors.append("unresolved dependency extra: " + name)
    reached, pending = set(), [config["name"]]
    while pending:
        name = pending.pop()
        if name not in reached:
            reached.add(name)
            pending.extend(edges.get(name, set()) - reached)
    if set(resolved) - reached:
        errors.append("orphan package records outside declared dependency closure")
    return sorted(set(errors))


def verify_dependencies(repo_root: Path | None = None) -> tuple[bool, list[str]]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]

    try:
        project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
        lock_bytes = (repo_root / "uv.lock").read_bytes()
        lock = tomllib.loads(lock_bytes.decode("utf-8"))
        approved = approved_names((repo_root / "docs/09-agent-execution/DEPENDENCY_ALLOWLIST.md").read_text(encoding="utf-8"))
        approval = project.get("tool", {}).get("campus247", {}).get("dependency-approval", {})
        approved_versions = set()
        approval_errors = []
        if approval:
            if (approval.get("reference") == APPROVAL_REFERENCE
                    and approval.get("candidate-lock-sha256") == APPROVED_CANDIDATE_SHA256
                    and hashlib.sha256(lock_bytes).hexdigest() == APPROVED_CANDIDATE_SHA256):
                approved_versions = {(p["name"], p["version"]) for p in lock["package"]
                                     if p["name"] != project["project"]["name"] and p["name"] not in approved}
                if len(approved_versions) != APPROVED_ADDITIONAL_PACKAGE_COUNT:
                    approval_errors.append("approved candidate package count differs")
                    approved_versions = set()
            else:
                approval_errors.append("human approval reference or candidate checksum mismatch")
        errors = approval_errors + validate_documents(project, lock, approved, approved_versions=approved_versions)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        return False, ["dependency input missing, malformed or policy unapproved; details suppressed"]
    return not errors, errors


def main() -> int:
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        print("Dependency verification requires Python >=3.12,<3.14", file=sys.stderr)
        return 1
    is_valid, errors = verify_dependencies()
    if is_valid:
        print("Dependency verification passed: approved exact pins, resolved closure, sources and artifact hashes.")
        return 0
    else:
        print("Dependency verification failed:", file=sys.stderr)
        for err in errors:
            print(f" - {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
