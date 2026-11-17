"""Read-only final source/version-control/build guard checks with fresh output."""
import hashlib
import json
import subprocess
import sys
from unified_ai_runtime_probe import ROOT, checked, retain

STATE=checked(ROOT/"infra/local/unified-ai-20261014-09")
NEW=["services/api/src/campus247/application/conversation/catalog.py",
 "services/api/src/campus247/application/assistance/consumer_contracts.py",
 "apps/web/src/lib/unified-assistant-runtime.tsx",
 "apps/web/src/features/assistance/UnifiedAssistantWorkspace.tsx",
 "apps/web/src/features/assistance/AssistantSettingsCenter.tsx",
 "apps/web/src/features/assistance/ResourceAssistant.tsx",
 "tests/integration/test_unified_consumers09.py","tests/unit/assistance/test_consumer_contracts09.py",
 "scripts/prepare_unified_ai_session09.py","scripts/preserve_unified09_extra.py","scripts/verify_unified_ai_session09.py",
 "scripts/prepare_unified_ai_frontend09.py","scripts/prepare_unified09_contracts.py","scripts/read_unified09_host.py","scripts/verify_unified09_scope.py"]

if __name__=="__main__":
    number=sys.argv[1]
    if number not in {"01","02"}: raise ValueError("fresh explicit scope attempt required")
    before=json.loads((STATE/"preflight.json").read_text(encoding="utf-8"))
    existing=[*before["sources"],*json.loads((STATE/"extra-preimages.json").read_text(encoding="utf-8"))]
    files=[item["path"] for item in existing]+NEW
    changes=[name for name in files if checked(ROOT/name).is_file() and (name in NEW or next((hashlib.sha256(checked(ROOT/name).read_bytes()).hexdigest()!=item["sha256"] for item in existing if item["path"]==name),False))]
    commands=[ ["git","status","--porcelain=v1"], ["git","diff","--name-only"],
        ["git","diff","--check","--",*[item["path"] for item in existing]],
        [sys.executable,"-B","-m","ruff","check","--select","E9,F","--no-cache",*[name for name in changes if name.endswith(".py")]] ]
    results=[]
    for command in commands:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
        results.append({"command":command,"exit_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr})
    guard=checked(ROOT/"infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    builds=[]
    for attempt in ("01","02","03","04","05"):
        folder=checked(STATE/('frontend'+attempt)/"acceptance-20261012-58-frontend-repair1-local-repair2")
        if (folder/".next/BUILD_ID").exists():
            builds.append({"attempt":attempt,"build_id":(folder/".next/BUILD_ID").read_text(),
                           "guard_unchanged":(folder/"preserve-build.mjs").read_bytes()==guard})
    missing=sorted(set(before["git_status"].splitlines())-set(results[0]["stdout"].splitlines()))
    value={"commands":results,"preexisting_git_entries_missing":missing,"builds":builds,"guard_sha256":hashlib.sha256(guard).hexdigest(),
           "source_files_changed_this_session":changes,"unchanged_preimage_files":[item["path"] for item in existing if item["path"] not in changes],
           "new_files":{name:hashlib.sha256(checked(ROOT/name).read_bytes()).hexdigest() for name in NEW}}
    retain(STATE/f"scope-verification-{number}.json",value)
    print(json.dumps({"checks":[r["exit_code"] for r in results],"missing":missing,"builds":builds},ensure_ascii=False))
    assert not missing and all(r["exit_code"]==0 for r in results) and all(row["guard_unchanged"] for row in builds)
