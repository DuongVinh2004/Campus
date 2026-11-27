"""Synthetic offline supply-chain checks; no downloads, installs or temp cleanup."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("dependency_gate", ROOT / "scripts/verify_dependencies.py")
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def package(name, version, dependencies=()):
    return {"name": name, "version": version, "source": {"registry": gate.REGISTRY},
            "dependencies": [{"name": dependency} for dependency in dependencies],
            "wheels": [{"url": f"https://files.pythonhosted.org/packages/synthetic/{name.replace('-', '_')}-{version}-py3-none-any.whl",
                        "hash": "sha256:" + "ab" * 32, "size": 100}]}


class DependencyGateTests(unittest.TestCase):
    def setUp(self):
        self.project = {"project": {"name": "campus247", "version": "0.1.0", "requires-python": gate.RUNTIME,
                                    "dependencies": ["fastapi==0.141.1"]},
                        "dependency-groups": {"dev": ["pytest==9.1.1"]}}
        self.root = {"name": "campus247", "version": "0.1.0", "source": {"virtual": "."},
                     "dependencies": [{"name": "fastapi"}], "dev-dependencies": {"dev": [{"name": "pytest"}]},
                     "metadata": {"requires-dist": [{"name": "fastapi", "specifier": "==0.141.1"}],
                                  "requires-dev": {"dev": [{"name": "pytest", "specifier": "==9.1.1"}]}}}
        self.lock = {"version": 1, "revision": 5, "requires-python": ">=3.12, <3.14",
                     "package": [self.root, package("fastapi", "0.141.1", ["starlette"]),
                                 package("starlette", "1.7.0"), package("pytest", "9.1.1")]}
        # Synthetic policy only; this does not approve starlette in repository policy.
        self.approved = {"fastapi", "starlette", "pytest"}

    def errors(self):
        return gate.validate_documents(self.project, self.lock, self.approved)

    def assert_denied(self, code):
        self.assertTrue(any(code in error for error in self.errors()), code)

    def test_complete_hash_pinned_closure(self):
        self.assertEqual(self.errors(), [])

    def test_approved_policy_includes_langgraph_without_self_approving_langchain(self):
        names = gate.approved_names((ROOT / "docs/09-agent-execution/DEPENDENCY_ALLOWLIST.md").read_text(encoding="utf-8"))
        self.assertIn("langgraph", names)
        self.assertNotIn("langchain-core", names)

    def test_unapproved_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            gate.approved_names('---\nstatus: "draft"\n---\n')

    def test_range_url_vcs_and_wildcard_are_rejected(self):
        for requirement in ("fastapi>=0.141", "fastapi==0.141.*", "fastapi @ https://example.invalid/a.whl",
                            "fastapi @ git+https://example.invalid/repo@main"):
            self.project["project"]["dependencies"] = [requirement]
            self.assert_denied("exact stable == pin")

    def test_empty_dependency_declarations_are_rejected(self):
        self.project["project"]["dependencies"] = []
        self.assert_denied("non-empty")

    def test_runtime_upper_bound_is_preserved(self):
        self.project["project"]["requires-python"] = ">=3.12"
        self.assert_denied("project runtime")

    def test_lock_runtime_drift_is_rejected(self):
        self.lock["requires-python"] = ">=3.12,<3.15"
        self.assert_denied("lock runtime")

    def test_virtual_root_references_are_not_resolved_records(self):
        self.lock["package"] = [self.root]
        self.assert_denied("unresolved declared dependency")

    def test_missing_root_is_rejected(self):
        self.lock["package"] = self.lock["package"][1:]
        self.assert_denied("matching virtual root")

    def test_missing_hash_is_rejected(self):
        self.lock["package"][1]["wheels"][0].pop("hash")
        self.assert_denied("hashed approved wheel")

    def test_wrong_algorithm_and_zero_hash_are_rejected(self):
        for value in ("md5:" + "ab" * 16, "sha256:" + "0" * 64):
            self.lock["package"][1]["wheels"][0]["hash"] = value
            self.assert_denied("hashed approved wheel")

    def test_unknown_registry_or_mutable_vcs_is_rejected(self):
        for source in ({"registry": "https://example.invalid/simple"}, {"git": "https://example.invalid/repo", "rev": "main"}):
            self.lock["package"][1]["source"] = source
            self.assert_denied("unapproved registry/VCS/path")

    def test_artifact_source_is_rejected_without_echoing_credentials(self):
        self.lock["package"][1]["wheels"][0]["url"] = "https://untrusted-user:untrusted-password@example.invalid/private.whl"
        self.assert_denied("hashed approved wheel")
        self.assertFalse(any("untrusted-password" in error or "private.whl" in error for error in self.errors()))

    def test_exact_version_drift_is_rejected(self):
        self.lock["package"][1]["version"] = "0.141.2"
        self.assert_denied("exact version differs")

    def test_requirement_metadata_drift_is_rejected(self):
        self.root["metadata"]["requires-dist"][0]["specifier"] = ">=0.141"
        self.assert_denied("production requirement metadata")

    def test_unknown_transitive_dependency_is_not_auto_approved(self):
        self.approved.remove("starlette")
        self.assert_denied("unapproved resolved dependency: starlette")

    def test_unresolved_transitive_edge_is_rejected(self):
        self.lock["package"][1]["dependencies"].append({"name": "missing-package"})
        self.assert_denied("unresolved dependency edge")

    def test_orphan_record_is_rejected(self):
        self.approved.add("orphan")
        self.lock["package"].append(package("orphan", "1.0"))
        self.assert_denied("orphan package")

    def test_duplicate_resolved_version_is_rejected(self):
        self.lock["package"].append(copy.deepcopy(self.lock["package"][1]))
        self.assert_denied("duplicate or ambiguous")

    def test_extra_request_drift_is_rejected(self):
        self.root["dependencies"][0]["extra"] = ["unexpected"]
        self.assert_denied("requested extras differ")

    def test_missing_or_malformed_inputs_fail_closed(self):
        with patch.object(Path, "read_text", side_effect=OSError("sensitive details")):
            valid, errors = gate.verify_dependencies(ROOT)
        self.assertFalse(valid)
        self.assertEqual(errors, ["dependency input missing, malformed or policy unapproved; details suppressed"])

    def test_new_source_override_is_rejected(self):
        self.project["tool"] = {"uv": {"sources": {"fastapi": {"git": "mutable"}}}}
        self.assert_denied("source overrides")

    def test_alternate_index_requires_separate_approval(self):
        self.project["tool"] = {"uv": {"index": [{"url": "https://example.invalid/simple"}]}}
        self.assert_denied("source overrides")

    def test_wheel_for_another_package_cannot_impersonate_approved_package(self):
        self.lock["package"][1]["wheels"][0]["url"] = "https://files.pythonhosted.org/packages/synthetic/foreign-1.0-py3-none-any.whl"
        self.assert_denied("hashed approved wheel")

    def test_version_scoped_approval_does_not_allow_a_future_version(self):
        self.approved.remove("starlette")
        versions = {("starlette", "1.7.0")}
        self.assertEqual(gate.validate_documents(self.project, self.lock, self.approved, approved_versions=versions), [])
        self.lock["package"][2]["version"] = "1.8.0"
        errors = gate.validate_documents(self.project, self.lock, self.approved, approved_versions=versions)
        self.assertIn("unapproved resolved dependency: starlette", errors)

    def test_repository_candidate_matches_exact_human_approval(self):
        valid, errors = gate.verify_dependencies(ROOT)
        self.assertTrue(valid, errors)

    def test_only_exact_otel_pairs_accept_prerelease_pins(self):
        for name, version in gate.APPROVED_OTEL_PRERELEASES:
            with self.subTest(name=name):
                errors = []
                parsed = gate._requirements([f"{name}=={version}"], errors, {(name, version)})
                self.assertEqual(errors, [])
                self.assertEqual(parsed[name]["specifier"], "==0.66b2")

    def test_otel_prerelease_without_version_approval_is_denied(self):
        errors = []
        gate._requirements(["opentelemetry-instrumentation==0.66b2"], errors)
        self.assertTrue(errors)

    def test_other_prereleases_remain_denied_even_with_version_approval(self):
        for name, version in (("foreign", "0.66b2"),
                              ("opentelemetry-instrumentation", "0.67b0"),
                              ("opentelemetry-instrumentation", "0.66b0"),
                              ("opentelemetry-instrumentation", "0.66rc0")):
            with self.subTest(name=name, version=version):
                errors = []
                gate._requirements([f"{name}=={version}"], errors, {(name, version)})
                self.assertTrue(errors)

    def test_transitive_otel_prerelease_requires_exact_version_approval(self):
        name, version = "opentelemetry-semantic-conventions", "0.66b2"
        self.lock["package"][1]["dependencies"] = [{"name": name}]
        self.lock["package"][2] = package(name, version)
        self.approved.add(name)
        self.assert_denied("immutable stable version required: " + name)
        self.assertEqual(gate.validate_documents(self.project, self.lock, self.approved,
                                                approved_versions={(name, version)}), [])
        self.lock["package"][2] = package(name, "0.67b0")
        errors = gate.validate_documents(self.project, self.lock, self.approved,
                                         approved_versions={(name, "0.67b0")})
        self.assertIn("immutable stable version required: " + name, errors)

    def test_missing_candidate_approval_denies_otel_prereleases(self):
        original = Path.read_text

        def changed(path, **kwargs):
            value = original(path, **kwargs)
            return value.split("[tool.campus247.dependency-approval]", 1)[0] if path == ROOT / "pyproject.toml" else value

        with patch.object(Path, "read_text", changed):
            valid, errors = gate.verify_dependencies(ROOT)
        self.assertFalse(valid)
        self.assertIn("immutable stable version required: opentelemetry-instrumentation", errors)

    def test_candidate_count_mismatch_does_not_enable_prerelease_exception(self):
        with patch.object(gate, "APPROVED_ADDITIONAL_PACKAGE_COUNT", 131):
            valid, errors = gate.verify_dependencies(ROOT)
        self.assertFalse(valid)
        self.assertIn("approved candidate package count differs", errors)
        self.assertIn("immutable stable version required: opentelemetry-instrumentation", errors)

    def test_candidate_bytes_drift_cannot_reuse_approval(self):
        original = Path.read_bytes

        def changed(path):
            value = original(path)
            return value + b"\n" if path == ROOT / "uv.lock" else value

        with patch.object(Path, "read_bytes", changed):
            valid, errors = gate.verify_dependencies(ROOT)
        self.assertFalse(valid)
        self.assertIn("human approval reference or candidate checksum mismatch", errors)
        self.assertIn("unapproved resolved dependency: langchain-core", errors)
        self.assertIn("immutable stable version required: opentelemetry-instrumentation", errors)

    def test_project_cannot_self_approve_a_different_candidate(self):
        original = Path.read_text

        def changed(path, **kwargs):
            value = original(path, **kwargs)
            return value.replace(gate.APPROVAL_REFERENCE, "unreviewed-reference") if path == ROOT / "pyproject.toml" else value

        with patch.object(Path, "read_text", changed):
            valid, errors = gate.verify_dependencies(ROOT)
        self.assertFalse(valid)
        self.assertIn("human approval reference or candidate checksum mismatch", errors)


if __name__ == "__main__":
    if not (3, 12) <= __import__("sys").version_info[:2] < (3, 14):
        raise SystemExit("approved Python >=3.12,<3.14 required")
    unittest.main(verbosity=2)
