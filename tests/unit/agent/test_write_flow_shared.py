"""Write-action confirmation across API processes: a preview made in one process is confirmed, once, in another.

Real separate processes (spawn). The checks that make confirmation safe stay: a wrong key, an unknown preview and a
second use are all refused. Step 1.8 prerequisite from the shared-state inventory.
"""
from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.agent.tools import write_flow  # noqa: E402
from campus247.domain.shared.values import generate_uuid7  # noqa: E402

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
ARGS = {"category": "ACADEMIC", "title": "Phúc khảo điểm thi"}
ACTOR = "019a0000-0000-7000-8000-0000000000aa"


def make_preview(database, key, queue):
    write_flow.configure_shared_state(database, key)
    broker = write_flow.WriteToolFlowBroker()
    preview = broker.build_preview(actor_id=ACTOR, tool_id="TOOL-TICKET-001", arguments=ARGS)
    token = broker.create_confirmation_interrupt(preview)["confirmation_token"]
    queue.put((preview, token))


def confirm(database, key, preview, token, queue):
    """Report 'ok' or the refusal text."""
    try:
        if key is not None:
            write_flow.configure_shared_state(database, key)
        write_flow.WriteToolFlowBroker().resume_with_confirmation(preview, ACTOR, ARGS, confirmation_token=token)
        queue.put("ok")
    except write_flow.ConfirmationBindingError as error:
        queue.put(str(error))


def run(target, *args):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=target, args=(*args, queue))
    process.start()
    result = queue.get(timeout=60)
    process.join(30)
    return result


@pytest.fixture
def database():
    base = ROOT / ".pytest-tmp-write-previews"
    base.mkdir(exist_ok=True)
    path = base / f"{generate_uuid7()}.sqlite3"
    yield path
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    try:
        base.rmdir()
    except OSError:
        pass


def test_preview_made_in_one_process_is_confirmed_once_in_another(database):
    preview, token = run(make_preview, database, KEY)
    assert run(confirm, database, KEY, preview, token) == "ok"
    assert "already been consumed" in run(confirm, database, KEY, preview, token)  # second use, third process


def test_a_different_signing_key_refuses_the_token(database):
    preview, token = run(make_preview, database, KEY)
    assert run(confirm, database, OTHER_KEY, preview, token) == "Confirmation token invalid"
    assert run(confirm, database, KEY, preview, token) == "ok"  # the refused attempt consumed nothing


def test_a_process_without_the_shared_state_still_fails_closed(database):
    preview, token = run(make_preview, database, KEY)
    assert run(confirm, database, None, preview, token) == "Preview binding is invalid"


def test_a_tampered_preview_is_refused(database):
    from dataclasses import replace
    preview, token = run(make_preview, database, KEY)
    forged = replace(preview, actor_user_id=generate_uuid7())  # the domain object already rejects a changed payload
    assert run(confirm, database, KEY, forged, token) == "Preview binding is invalid"


def test_concurrent_confirmations_have_exactly_one_winner(database):
    preview, token = run(make_preview, database, KEY)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=confirm, args=(database, KEY, preview, token, queue)) for _ in range(4)]
    for process in processes:
        process.start()
    results = [queue.get(timeout=60) for _ in processes]
    for process in processes:
        process.join(30)
    assert results.count("ok") == 1
    assert all("already been consumed" in result for result in results if result != "ok")


def test_default_state_is_per_process_and_unchanged():
    broker = write_flow.WriteToolFlowBroker()
    preview = broker.build_preview(actor_id=ACTOR, tool_id="TOOL-TICKET-001", arguments=ARGS)
    token = broker.create_confirmation_interrupt(preview)["confirmation_token"]
    assert broker.resume_with_confirmation(preview, ACTOR, ARGS, confirmation_token=token).is_authorized
    with pytest.raises(write_flow.ConfirmationBindingError):
        broker.resume_with_confirmation(preview, ACTOR, ARGS, confirmation_token=token)


def test_short_shared_key_is_rejected(database):
    with pytest.raises(ValueError):
        write_flow.configure_shared_state(database, b"short")
