"""The published case boundary must match the models used by real consumers."""
import json
from pathlib import Path

import pytest

from campus247.application.assistance import case_contracts as case
from campus247.application.assistance.scoped_context import ContextRequest

MODELS = [case.BatchConfirm, case.BatchPrepare, case.CaseConfirm, case.CaseDraftPrepare, case.CaseDraftPreview,
          case.CaseDraftRead, ContextRequest, case.HandoverSummary, case.ItemResponse, case.NotificationOpen,
          case.QueueRead, case.ReceiptRead, case.StaffIntent, case.SupplementItem, case.SupplementResponse]


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__name__)
def test_case_contract_export_exactly_matches_actual_boundary_model(model):
    path = Path(__file__).resolve().parents[2] / "contracts/json-schema/assistance/cases-v13-02" / (model.__name__ + ".schema.json")
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported == model.model_json_schema()
    assert exported["additionalProperties"] is False
