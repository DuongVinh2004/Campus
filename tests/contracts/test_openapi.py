from __future__ import annotations

import copy
from pathlib import Path
import pytest

from contracts.tools.validate_openapi import (
    OPENAPI_PATH,
    REQUIREMENTS_PATH,
    SECURITY_CONTROLS_PATH,
    TASK_ITEMS,
    load_document,
    validate_local_refs,
    validate_operations,
)

ROOT = Path(__file__).resolve().parents[2]


def inline_operations(document: dict) -> list[dict]:
    """Operations written inside the document (path items that are only a $ref to another file have none here)."""
    return [value for item in document["paths"].values() if isinstance(item, dict)
            for value in item.values() if isinstance(value, dict) and "responses" in value]


@pytest.fixture(scope="module")
def openapi_doc() -> dict:
    return load_document(OPENAPI_PATH)


@pytest.fixture(scope="module")
def validation_catalogs() -> tuple[set[str], set[str], set[str]]:
    requirements = load_document(REQUIREMENTS_PATH)
    req_ids = {
        item["id"]
        for item in requirements.get("requirements", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    import re
    ctrl_ids = set(
        re.findall(
            r"^\|\s*`(SEC-CTRL-[0-9]{3})`\s*\|",
            SECURITY_CONTROLS_PATH.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    )
    test_ids = {p.stem for p in TASK_ITEMS.glob("TASK-TEST-*.yaml")}
    return req_ids, ctrl_ids, test_ids


def test_openapi_positive_validation(
    openapi_doc: dict, validation_catalogs: tuple[set[str], set[str], set[str]]
):
    """Verify OpenAPI 3.1.2 specification is structurally valid with all local references resolved."""
    req_ids, ctrl_ids, test_ids = validation_catalogs
    op_count = validate_operations(openapi_doc, req_ids, ctrl_ids, test_ids)
    assert op_count >= 30

    cache = {OPENAPI_PATH.resolve(): openapi_doc}
    ref_count = validate_local_refs(OPENAPI_PATH, cache)
    assert ref_count > 0


def test_openapi_negative_invalid_version(
    openapi_doc: dict, validation_catalogs: tuple[set[str], set[str], set[str]]
):
    """Verify validator rejects invalid OpenAPI version."""
    req_ids, ctrl_ids, test_ids = validation_catalogs
    mutated = copy.deepcopy(openapi_doc)
    mutated["openapi"] = "3.0.0"
    with pytest.raises(ValueError, match="OpenAPI version must be exactly 3.1.2"):
        validate_operations(mutated, req_ids, ctrl_ids, test_ids)


def test_openapi_negative_missing_problem_response(
    openapi_doc: dict, validation_catalogs: tuple[set[str], set[str], set[str]]
):
    """Verify validator rejects operation lacking RFC 9457 Problem error response."""
    req_ids, ctrl_ids, test_ids = validation_catalogs
    mutated = copy.deepcopy(openapi_doc)
    first_op = inline_operations(mutated)[0]
    # Remove Problem error response
    first_op["responses"] = {"200": {"description": "OK"}}
    with pytest.raises(ValueError, match="RFC 9457 Problem error response is required"):
        validate_operations(mutated, req_ids, ctrl_ids, test_ids)


def test_openapi_negative_duplicate_operation_id(
    openapi_doc: dict, validation_catalogs: tuple[set[str], set[str], set[str]]
):
    """Verify validator rejects duplicate operationId."""
    req_ids, ctrl_ids, test_ids = validation_catalogs
    mutated = copy.deepcopy(openapi_doc)
    op1, op2 = inline_operations(mutated)[:2]
    op2["operationId"] = op1["operationId"]
    with pytest.raises(ValueError, match="duplicate operationId"):
        validate_operations(mutated, req_ids, ctrl_ids, test_ids)
