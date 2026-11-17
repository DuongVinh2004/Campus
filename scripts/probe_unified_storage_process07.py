"""One bounded storage fixture worker, never a model/application writer."""
import argparse
import sys
import time

from unified_ai_runtime_probe import ROOT, checked, retain

sys.path[:0] = [str(checked(ROOT / "services/api/src")),str(checked(ROOT / "packages/synthetic/src"))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind",choices=["preferences","resume"],required=True)
    for flag in ("database","gate","ready","output","client","run","conversation","fixture-root"):
        parser.add_argument("--"+flag,required=True)
    args = parser.parse_args()
    from pathlib import Path
    database,gate,ready,output = [checked(Path(value)) for value in (args.database,args.gate,args.ready,args.output)]
    fixture_root = checked(Path(args.fixture_root))
    assert fixture_root.is_relative_to(checked(ROOT / "infra/local")) and fixture_root != checked(ROOT / "infra/local")
    assert all(path.parent == fixture_root for path in (database,gate,ready,output)) and database.name == "process.sqlite3"
    assert database.is_file() and not ready.exists() and not output.exists()
    retain(ready,{"ready":True})
    deadline = time.monotonic()+10
    while not gate.exists():
        if time.monotonic() >= deadline: raise TimeoutError("fixture gate unavailable")
        time.sleep(.02)
    if args.kind == "preferences":
        from campus247.application.assistance.state_storage import (
            StateScope,
            StorageConflict,
        )
        from campus247.infrastructure.repositories.sqlite_actor_state import (
            SQLiteActorStateStore,
        )
        try:
            receipt = SQLiteActorStateStore(database).commit(StateScope("huce-local-public","4b419a1b-6d41-7dfb-8943-2edd9f071385"),
                "preferences","account",0,{"locale":"en"},args.client)
            result = {"state":"committed","receipt_id":receipt.receipt_id,"version":receipt.version}
        except StorageConflict:
            result = {"state":"conflict"}
    else:
        from campus247.infrastructure.repositories.sqlite_agent_runs import (
            RunConflict,
            SQLiteAgentRunStore,
        )
        try:
            version = SQLiteAgentRunStore(database,tenant="huce-local-public").claim_resume(args.run,
                "4b419a1b-6d41-7dfb-8943-2edd9f071385",args.conversation,2,10)
            result = {"state":"claimed","version":version}
        except RunConflict:
            result = {"state":"conflict"}
    retain(output,result)


if __name__ == "__main__":
    main()
