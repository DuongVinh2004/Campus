"""Read-only local readback; retain fresh evidence, never reset business data."""
import difflib
import json
import sys
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

from unified_ai_runtime_probe import ROOT, checked, http, retain
from unified_ai_session02_preflight import STATE
from verify_unified_ai_candidate import database_digest, status

sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.application.assistance.unified_contracts import CONTRACT_MODELS
from campus247.application.assistance.baseline import BaselineStart, BaselineEvent


def verify():
    before = json.loads(checked(STATE / "preflight-01.json").read_text(encoding="utf-8"))
    launch = json.loads(checked(STATE / "runtime-launch-02.json").read_text(encoding="utf-8"))
    build = json.loads(checked(STATE / "frontend-build-03.json").read_text(encoding="utf-8"))
    snapshot = checked(ROOT / launch["frontend"])
    build_id = checked(snapshot / ".next/BUILD_ID").read_text().strip()
    assert build["exit_code"] == 0 and build_id == launch["build_id"]
    assert checked(snapshot / "preserve-build.mjs").read_bytes() == checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    source_files = ["src/features/documents/ServiceWorkspace.tsx", "src/features/assistance/BaselineRecorder.tsx",
                    "src/features/assistance/AssistanceContextPanel.tsx", "src/lib/unified-ai-contracts.ts", "src/lib/api/client.ts"]
    for file in source_files:
        assert checked(ROOT / "apps/web" / file).read_bytes() == checked(snapshot / file).read_bytes(), file

    reports = []
    unique = {"backend":set(), "frontend":set()}
    for name, group in [("backend-tests-01.xml","backend"), ("backend-tests-02.xml","backend"),
                        ("baseline-final-tests-01.xml","backend"), ("proxy-tests-01.xml","backend"),
                        ("frontend-tests-03.xml","frontend")]:
        suites = list(ET.parse(checked(STATE / name)).getroot().iter("testsuite"))
        counts = {key:sum(int(s.get(key,"0")) for s in suites) for key in ["tests","failures","errors","skipped"]}
        assert counts["failures"] == counts["errors"] == counts["skipped"] == 0
        for suite in suites:
            for case in suite.findall("testcase"):
                unique[group].add((case.get("classname"),case.get("name")))
        reports.append({"path":name, **counts})
    schemas = []
    for name, model in {**CONTRACT_MODELS,"BaselineStart":BaselineStart,"BaselineEvent":BaselineEvent}.items():
        path = checked(ROOT / "contracts/json-schema/assistance/unified-core-v1" / (name+".schema.json"))
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document == {"$schema":"https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()}, name
        schemas.append(name)

    code, runtime = http(8006,"/v1/assistant/runtime")
    assert code == 200 and runtime["frontend_build_id"] == build_id and runtime["owns_paid_ledger"] is False
    code, openapi = http(8006,"/openapi.json")
    assert code == 200
    operations = [op["operationId"] for path in openapi["paths"].values() for op in path.values() if isinstance(op,dict) and "operationId" in op]
    assert len(operations) == len(set(operations)), "duplicate operation IDs"
    tokens = {}
    for alias in ["SV001","SV024","OF001","OF002"]:
        code, login = http(8006,"/v1/auth/demo-login",body={"account":alias})
        assert code == 200
        tokens[alias] = login["token"]
    headers = {"Authorization":"Bearer " + tokens["SV001"]}
    with urlopen(Request("http://127.0.0.1:8006/v1/assistant/contracts",headers=headers),timeout=8) as response:
        assert response.headers["Cache-Control"] == "no-store"
        contract_registry = json.load(response)
    assert contract_registry["execution_authority"] == "none"
    code, _ = http(8006,"/v1/assistant/baseline/sessions")
    assert code == 401
    code, _ = http(8006,"/v1/assistant/baseline/sessions",tokens["SV001"],{"client_id":"invalid","case_id":"UB-04","operator_kind":"human_declared","user_confirmed":True})
    assert code == 422
    code, records = http(8006,"/v1/service-requests",tokens["SV001"])
    assert code == 200
    record = next(r for r in records["items"] if r["document_type"] == "GRADE_APPEAL")
    request = {"surface":"service","resource":{"kind":"service_request","id":record["id"],"expected_version":record["version"]}}
    contexts = {}
    for alias in ["SV001","OF002"]:
        code, context = http(8006,"/v1/assistant/context",tokens[alias],request)
        assert code == 200 and context["action_authority"] == "none"
        assert not any(key in context for key in ["preview","token","profile","internal_notes"])
        contexts[alias] = context
    assert contexts["SV001"]["resource"]["view"] == "student"
    assert contexts["OF002"]["resource"]["view"] == "staff"
    assert contexts["SV001"]["evidence"] == contexts["OF002"]["evidence"]
    for alias in ["SV024","OF001"]:
        code, _ = http(8006,"/v1/assistant/context",tokens[alias],request)
        assert code == 404
    code, _ = http(8006,"/v1/assistant/context",tokens["SV001"],{**request,"resource":{**request["resource"],"expected_version":record["version"]+1}})
    assert code == 409

    identifier = "01a138e5-5aee-7ba8-9db7-a582d71a2b56"
    code, measurement = http(8006,f"/v1/assistant/baseline/sessions/{identifier}",tokens["OF002"])
    assert code == 200 and measurement["operator_kind"] == "automation" and measurement["state"] == "finished"
    code, receipts = http(8006,f"/v1/assistant/baseline/sessions/{identifier}/receipts",tokens["OF002"])
    assert code == 200
    sums = {key:0 for key in ["active_ms","wait_ms","paused_ms","unattributed_ms"]}
    for receipt in receipts["items"]:
        metric = {"active":"active_ms", "waiting":"wait_ms", "paused":"paused_ms", "unattributed":"unattributed_ms"}[receipt["interval_classification"]]
        sums[metric] += receipt["interval_ms"]
    assert all(measurement[key] == value for key,value in sums.items())
    assert len(receipts["items"]) == measurement["event_count"]
    assert [r["sequence"] for r in receipts["items"]] == list(range(1,measurement["event_count"]+1))
    assert "owner" not in measurement and "tenant" not in measurement and "client_id" not in measurement
    for alias in ["SV001","SV024","OF001"]:
        for suffix in ["", "/receipts"]:
            code, _ = http(8006,f"/v1/assistant/baseline/sessions/{identifier}"+suffix,tokens[alias])
            assert code == 404

    prior_tables = database_digest(checked(STATE / "business-before-01.sqlite3"))
    current_tables = database_digest(checked(ROOT / launch["database"]))
    differences = [name for name, value in prior_tables.items() if current_tables.get(name) != value]
    assert not differences, "pre-existing business data changed; inspect, never reset: " + repr(differences)
    added = sorted(set(current_tables)-set(prior_tables))
    assert added == ["unified_baseline_event","unified_baseline_session"]
    current_git = status()
    missing = sorted(set(before["git_status"].splitlines())-set(current_git.splitlines()))
    assert not missing, "pre-existing version-control state changed: " + repr(missing)
    patches = []
    for file in before["source_backups"]:
        original = checked(STATE / file["backup"]).read_text(encoding="utf-8")
        current = checked(ROOT / file["path"]).read_text(encoding="utf-8")
        patch = "".join(difflib.unified_diff(original.splitlines(True),current.splitlines(True),fromfile=file["backup"],tofile=file["path"]))
        if patch:
            patches.append({"path":file["path"],"patch":patch})
    return {"scope":"local_synthetic_contracts_and_opt_in_measurement","build_id":build_id,"runtime":runtime,
        "test_reports":reports,"unique_backend_tests":len(unique["backend"]),"unique_frontend_tests":len(unique["frontend"]),
        "unique_total_tests":sum(len(items) for items in unique.values()),"schemas_match_models":schemas,
        "openapi_unique_operation_ids":len(operations),"frontend_source_matches_build":source_files,
        "guard_unchanged":True,"preexisting_git_entries_preserved":True,"git_status":current_git,"scoped_patches":patches,
        "preexisting_business_tables_unchanged":prior_tables,"additive_tables":added,
        "context_role_isolation_and_stale_checks":True,"contract_registry_no_store":True,
        "automation_measurement":{"id":identifier,"version":measurement["version"],"event_count":measurement["event_count"],"receipt_sums_match":True,"actor_isolation":True},
        "human_baseline_captured_by_agent":False,"user_trial_method":"user will self-test locally",
        "paid_model_calls":0,"production_changes":False,"limitations":["Recorder state is not proven attention or human identity", "Only hooked service operations are counted; not every DOM click", "Human baseline and usability acceptance remain pending", "Schemas and proposals do not implement execution capabilities", "Candidate is a retained snapshot, not automatic synchronization with app8004"]}


if __name__ == "__main__":
    output = checked(STATE / "candidate-verification-01.json")
    if output.exists():
        raise FileExistsError("retained evidence must not be overwritten")
    report = verify()
    retain(output,report)
    print(json.dumps({"build_id":report["build_id"],"tests":report["unique_total_tests"],"evidence":str(output)}))
