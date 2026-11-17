"""Worker process for test_sqlite_multiprocess: hammer one SQLite store with writes, report the outcome as JSON.

Usage: python sqlite_concurrency_worker.py <store> <database path> <worker id> <writes>
Prints {"ok": n, "errors": {"ErrorType": count}, ...} on the last line. Never raises: failures are the measurement.
"""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for extra in ("services/api/src", "packages/synthetic/src"):
    sys.path.insert(0, str(ROOT / extra))

STORE, PATH, WORKER, WRITES = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
OWNER = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
STATE_OWNER = "019a0000-0000-7000-8000-000000000007"


async def conversations(errors):
    from campus247.application.conversation.messages import ConversationMessageService, SenderType
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    service = ConversationMessageService(SQLiteConversationRepository(PATH))
    done = 0
    for i in range(WRITES):
        try:
            conv = await service.create_conversation(owner_user_id=OWNER)
            await service.append_message(conversation_id=conv.id, sender_type=SenderType.USER, content=f"w{WORKER}-{i}",
                                         sender_user_id=OWNER)
            done += 1
        except Exception as exc:  # noqa: BLE001 -- the failure type is the result
            errors[type(exc).__name__] += 1
    return done, {}


async def conversation_readers(errors):
    """Reads (list conversations, list messages) while other processes write."""
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    repo = SQLiteConversationRepository(PATH)
    done = 0
    for _ in range(WRITES):
        try:
            for conv in (await repo.list_owned_conversations(OWNER))[:3]:
                await repo.list_messages(conv.id)
            done += 1
        except Exception as exc:  # noqa: BLE001
            errors[type(exc).__name__] += 1
    return done, {}


async def actor_state(errors):
    """Each worker commits its own keys; all workers also race on one shared key (exactly one winner per version)."""
    from campus247.application.assistance.state_storage import StateScope
    from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
    from campus247.domain.shared.values import generate_uuid7
    store = SQLiteActorStateStore(PATH)
    scope = StateScope("huce-local-public", STATE_OWNER)
    done, race_wins = 0, 0
    for i in range(WRITES):
        try:
            store.commit(scope, "preferences", f"own-{WORKER}-{i}", 0, {"locale": "vi"}, generate_uuid7())
            done += 1
        except Exception as exc:  # noqa: BLE001
            errors[type(exc).__name__] += 1
    for version in range(WRITES):
        try:
            store.commit(scope, "preferences", "shared", version, {"locale": "vi" if version % 2 else "en"}, generate_uuid7())
            race_wins += 1
        except Exception as exc:  # noqa: BLE001 -- losing the race is a version conflict, not a storage failure
            errors[type(exc).__name__] += 1
    return done, {"race_wins": race_wins}


async def idempotency(errors):
    """Every worker reserves its own keys, and all race on the same ones: each shared key has exactly one creator."""
    from campus247.application.action.idempotency import IdempotencyLedger
    ledger = IdempotencyLedger(PATH)
    done, created_shared = 0, 0
    for i in range(WRITES):
        try:
            ledger.reserve("actor-1", "op", f"own-{WORKER}-{i:04d}-0000000", "fingerprint")
            done += 1
        except Exception as exc:  # noqa: BLE001
            errors[type(exc).__name__] += 1
        try:
            if ledger.reserve("actor-1", "op", f"shared-{i:04d}-000000000", "fingerprint").status.value == "ACQUIRED":
                created_shared += 1
        except Exception as exc:  # noqa: BLE001
            errors[type(exc).__name__] += 1
    return done, {"created_shared": created_shared}


async def main():
    errors = Counter()
    mode = {"conversations": conversations, "conversation_readers": conversation_readers,
            "actor_state": actor_state, "idempotency": idempotency}[STORE]
    done, extra = await mode(errors)
    print(json.dumps({"ok": done, "errors": dict(errors), **extra}))


asyncio.run(main())
