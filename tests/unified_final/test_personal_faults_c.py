"""C adversarial timing on B core, distinct from still-pending shared wiring."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import generate_uuid7
from tests.unified_personal13b.test_memory_tracking import env as memory_fixture, tracking as tracking_fixture
from tests.unified_personal13b.test_memory_tracking import control, save, query, subscribe, worker

env = memory_fixture
tracking = tracking_fixture


@pytest.mark.parametrize("late_change", ["temporary", "consent", "session"])
def test_memory_use_rechecks_late_mode_consent_and_revocation_without_callback(env, late_change):
    control(env)
    save(env)
    prior = env.memory.retrieve(env.actor, query())
    called = []
    if late_change == "temporary":
        env.mode = "temporary"
    elif late_change == "consent":
        env.consent = False
    else:
        env.revoked = True
    with pytest.raises(CertificateError):
        env.memory.use(env.actor, query(), prior["sha256"], lambda value: called.append(value))
    assert called == []


@pytest.mark.parametrize("late_change", ["recipient", "session"])
def test_worker_final_projection_rechecks_recipient_and_revocation_before_insert(tracking, late_change):
    state = tracking
    subscribe(state)
    state.source.emit(state.actor, state.target)
    original = state.tracking.project_notification
    calls = []
    def changing_projection(actor, spec, event):
        value = original(actor, spec, event)
        calls.append(event.event_id)
        if late_change == "recipient" and len(calls) == 2:
            return value.model_copy(update={"recipient_id": generate_uuid7()})
        if late_change == "session" and len(calls) == 1:
            state.revoked = True
        return value
    state.tracking.project_notification = changing_projection
    result = worker(state).tick()
    assert result["delivered"] == 0 and result["suppressed"] == 1
    with sqlite3.connect(state.tracking_store.path.as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tracking_inbox").fetchone()[0] == 0


def test_two_worker_instances_deliver_once_under_contention(tracking):
    state = tracking
    subscribe(state)
    state.source.emit(state.actor, state.target)
    workers = [worker(state), worker(state)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda instance: instance.tick(), workers))
    assert sum(value["delivered"] for value in results) == 1
    with sqlite3.connect(state.tracking_store.path.as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tracking_inbox").fetchone()[0] == 1
    assert len(state.tracking.notifications(state.actor)["items"]) == 1
