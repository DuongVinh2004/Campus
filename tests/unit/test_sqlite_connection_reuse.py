"""Connection reuse for the hot SQLite stores (step 1.9 follow-up): same results, same guards, no shared transactions."""
import sqlite3
import threading
import time

import pytest

from campus247.infrastructure.repositories.sqlite_reuse import ReusableConnections


class Counter:
    def __init__(self):
        self.opened = []

    def __call__(self):
        connection = sqlite3.connect(":memory:")
        self.opened.append(connection)
        return connection


def test_a_connection_is_reused_until_the_ttl_then_reopened():
    pool, opener = ReusableConnections(ttl_s=0.1), Counter()
    first, temporary = pool.checkout(opener)
    pool.release(first, temporary, failed=False)
    second, temporary = pool.checkout(opener)
    pool.release(second, temporary, failed=False)
    assert first is second and len(opener.opened) == 1
    time.sleep(0.15)
    third, temporary = pool.checkout(opener)
    pool.release(third, temporary, failed=False)
    assert third is not first and len(opener.opened) == 2


def test_nested_use_gets_its_own_connection_and_cannot_touch_the_outer_transaction():
    pool, opener = ReusableConnections(), Counter()
    outer, outer_temporary = pool.checkout(opener)
    outer.execute("CREATE TABLE t(a)")
    outer.execute("BEGIN")
    outer.execute("INSERT INTO t VALUES (1)")
    inner, inner_temporary = pool.checkout(opener)
    assert inner is not outer and inner_temporary and not outer_temporary
    inner.commit()                      # committing the inner one must not commit the outer one's work
    assert outer.in_transaction
    pool.release(inner, inner_temporary, failed=False)
    pool.release(outer, outer_temporary, failed=False)


def test_failure_retires_the_connection():
    pool, opener = ReusableConnections(), Counter()
    first, temporary = pool.checkout(opener)
    pool.release(first, temporary, failed=True)
    second, _ = pool.checkout(opener)
    assert second is not first and len(opener.opened) == 2
    with pytest.raises(sqlite3.ProgrammingError):
        first.execute("SELECT 1")       # the failed one was closed


def test_invalidate_retires_cached_connections():
    pool, opener = ReusableConnections(), Counter()
    first, temporary = pool.checkout(opener)
    pool.release(first, temporary, failed=False)
    pool.invalidate()
    second, _ = pool.checkout(opener)
    assert second is not first


def test_each_thread_has_its_own_connection():
    pool, opener = ReusableConnections(), Counter()
    seen = []

    def work():
        connection, temporary = pool.checkout(opener)
        seen.append(connection)
        pool.release(connection, temporary, failed=False)

    main, temporary = pool.checkout(opener)
    pool.release(main, temporary, failed=False)
    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert seen[0] is not main


def test_stores_keep_their_behaviour_with_reuse(tmp_path):
    """Real stores: repeated and nested connect() calls behave exactly as with fresh connections."""
    import asyncio
    from pathlib import Path

    from campus247.application.conversation.messages import ConversationMessageService, SenderType
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository

    root = Path(__file__).resolve().parents[2] / ".pytest-tmp-reuse"
    root.mkdir(exist_ok=True)
    database = root / f"c-{time.time_ns()}.sqlite3"
    try:
        repository = SQLiteConversationRepository(database)
        service = ConversationMessageService(repository)
        owner = "4b419a1b-6d41-7dfb-8943-2edd9f071385"

        async def run():
            ids = []
            for index in range(5):
                conversation = await service.create_conversation(owner_user_id=owner)
                await service.append_message(conversation_id=conversation.id, sender_type=SenderType.USER, content=f"m{index}",
                                             sender_user_id=owner)
                ids.append(conversation.id)
            return ids

        ids = asyncio.run(run())
        assert len(ids) == 5 and len(asyncio.run(repository.list_owned_conversations(owner))) == 5
        assert all(len(asyncio.run(repository.list_messages(i))) == 1 for i in ids)
        with repository.connect() as outer:
            outer.execute("BEGIN IMMEDIATE")
            with repository.connect() as inner:            # nested: its own connection (it only reads)
                assert inner is not outer
                assert inner.execute("SELECT COUNT(*) FROM conversation").fetchone()[0] == 5
            assert outer.in_transaction
    finally:
        repository._connections.close_current_thread()
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(database) + suffix).unlink(missing_ok=True)
        try:
            root.rmdir()
        except OSError:
            pass
