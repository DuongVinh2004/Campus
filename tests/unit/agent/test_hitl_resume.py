from __future__ import annotations

import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from campus247.agent.hitl.interrupts import (
    DurableInterruptManager,
    InterruptRecord,
    InterruptStatus,
    ReviewDecision,
    ReviewerRole,
)


def test_interrupt_survives_process_restart():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Process 1 creates interrupt
        mgr1 = DurableInterruptManager(storage_dir=tmp_dir)
        rec = mgr1.create_interrupt(
            session_id="sess-100",
            turn_id="turn-100",
            state_version=1,
            reason="High risk room booking",
            min_role=ReviewerRole.STAFF,
            summary="Booking auditorium for 500 people",
            payload={"room_id": "AUD-01", "action": "book"},
            expires_in_seconds=3600,
        )
        assert rec.status == InterruptStatus.PENDING

        # Process 2 starts up fresh with same storage
        mgr2 = DurableInterruptManager(storage_dir=tmp_dir)
        loaded = mgr2.get_interrupt(rec.interrupt_id)
        assert loaded is not None
        assert loaded.interrupt_id == rec.interrupt_id
        assert loaded.state_version == 1
        assert loaded.min_role == ReviewerRole.STAFF
        assert loaded.summary == "Booking auditorium for 500 people"
        assert loaded.status == InterruptStatus.PENDING


def test_only_authorized_reviewer_can_advance_exact_version():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = DurableInterruptManager(storage_dir=tmp_dir)
        rec = mgr.create_interrupt(
            session_id="sess-200",
            turn_id="turn-200",
            state_version=2,
            reason="Administrative override",
            min_role=ReviewerRole.ADMIN,
            summary="Access privileged student files",
            payload={"student_id": "S123"},
            expires_in_seconds=1800,
        )

        # 1. Reject insufficient role (STAFF < ADMIN)
        with pytest.raises(PermissionError, match="Insufficient reviewer role"):
            mgr.resolve_interrupt(
                interrupt_id=rec.interrupt_id,
                decision=ReviewDecision.APPROVED,
                reviewer_id="staff-user-1",
                reviewer_role=ReviewerRole.STAFF,
                expected_state_version=2,
            )

        # 2. Reject mismatched state version
        with pytest.raises(ValueError, match="State version mismatch"):
            mgr.resolve_interrupt(
                interrupt_id=rec.interrupt_id,
                decision=ReviewDecision.APPROVED,
                reviewer_id="admin-user-1",
                reviewer_role=ReviewerRole.ADMIN,
                expected_state_version=1,  # Stale version
            )

        # 3. Authorized reviewer with exact version succeeds
        resolved = mgr.resolve_interrupt(
            interrupt_id=rec.interrupt_id,
            decision=ReviewDecision.APPROVED,
            reviewer_id="admin-user-1",
            reviewer_role=ReviewerRole.ADMIN,
            expected_state_version=2,
        )
        assert resolved.status == InterruptStatus.APPROVED
        assert resolved.state_version == 3  # Advanced
        assert resolved.resolved_by == "admin-user-1"


def test_duplicate_or_stale_review_causes_no_repeated_execution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = DurableInterruptManager(storage_dir=tmp_dir)
        rec = mgr.create_interrupt(
            session_id="sess-300",
            turn_id="turn-300",
            state_version=1,
            reason="Controlled write check",
            min_role=ReviewerRole.STAFF,
            summary="Submit document request",
            payload={"doc_type": "transcript"},
            expires_in_seconds=1800,
        )

        execution_counter = 0

        def dummy_action():
            nonlocal execution_counter
            execution_counter += 1
            return {"action": "executed"}

        # First resolution executes action
        res1 = mgr.resolve_and_execute(
            interrupt_id=rec.interrupt_id,
            decision=ReviewDecision.APPROVED,
            reviewer_id="staff-1",
            reviewer_role=ReviewerRole.STAFF,
            expected_state_version=1,
            action_handler=dummy_action,
        )
        assert execution_counter == 1
        assert res1.status == InterruptStatus.APPROVED

        # Duplicate resolution attempt should be rejected without re-executing action
        with pytest.raises(RuntimeError, match="Interrupt already resolved"):
            mgr.resolve_and_execute(
                interrupt_id=rec.interrupt_id,
                decision=ReviewDecision.APPROVED,
                reviewer_id="staff-1",
                reviewer_role=ReviewerRole.STAFF,
                expected_state_version=1,
                action_handler=dummy_action,
            )

        assert execution_counter == 1  # No repeated execution


def test_execute_handover_node_contact_fix() -> None:
    from campus247.agent.nodes.definitions import execute_handover_node
    from campus247.agent.state import AgentState, NormalizedTurn, SafetyDecision, SafetySeverity
    from campus247.ports.contact import ContactConfigPort, ContactInfo, AlertPort

    class FakeContactPort(ContactConfigPort):
        def get_emergency_contact(self):
            return ContactInfo(phone="113", description="Cảnh sát")
            
    class FakeAlertPort(AlertPort):
        def __init__(self):
            self.alerts = []
        def emit_operational_alert(self, code: str, message: str) -> None:
            self.alerts.append(code)

    state = AgentState(
        request=NormalizedTurn(session_id="s", turn_id="t", user_id="u", query="q"),
        safety=SafetyDecision(is_crisis=True, severity=SafetySeverity.CRITICAL)
    )
    
    # Missing ports
    alert_port = FakeAlertPort()
    next_state = execute_handover_node(state, contact_port=None, alert_port=alert_port)
    assert "MISSING_CONTACT_PORT" in alert_port.alerts
    assert "113" not in next_state.draft.text
    
    # Missing contact in port
    class EmptyContactPort(ContactConfigPort):
        def get_emergency_contact(self):
            return None
    alert_port2 = FakeAlertPort()
    next_state2 = execute_handover_node(state, contact_port=EmptyContactPort(), alert_port=alert_port2)
    assert "MISSING_EMERGENCY_CONTACT" in alert_port2.alerts
    assert "113" not in next_state2.draft.text
    
    # Success
    next_state3 = execute_handover_node(state, contact_port=FakeContactPort())
    assert "113" in next_state3.draft.text
    assert "Cảnh sát" in next_state3.draft.text


def test_non_crisis_high_without_contact_does_not_claim_maintenance() -> None:
    from campus247.agent.nodes.definitions import execute_handover_node
    from campus247.agent.state import AgentState, NormalizedTurn, SafetyDecision, SafetySeverity

    state = AgentState(
        request=NormalizedTurn(session_id="s", turn_id="t", user_id="u", query="q"),
        safety=SafetyDecision(is_crisis=False, severity=SafetySeverity.HIGH, reason="financial_impact"),
    )
    text = execute_handover_node(state, contact_port=None).draft.text
    assert "bảo trì" not in text
    crisis = AgentState(
        request=state.request,
        safety=SafetyDecision(is_crisis=True, severity=SafetySeverity.CRITICAL),
    )
    assert "bảo trì" in execute_handover_node(crisis, contact_port=None).draft.text
