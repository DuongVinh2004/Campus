"""Regression: sharing a download must not erase the K71 publication row."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from complete_huce_corpus import cohorts_for, publication_bindings


def manifest():
    return json.loads((ROOT / "data/huce-discovery-20261020/curricula-20261020T153323371137Z/manifest.json")
        .read_text(encoding="utf-8"))


def test_shared_pdf_retains_both_publication_rows_but_only_proves_k71():
    data = manifest()
    identifiers = {"1CoFsdOzqixs2B5srF8bFE8mvg3lw1llE", "1Ops439XuuII7cNZ7A-jenN_PSN1oxFQt",
        "1dAWTe8JcrV07ndAXCQjGF3liC2dd3YjW", "1nPJqjaUqzlYIvT4OR1YMFoBjnP4yysxb"}
    for file in data["files"]:
        if file["drive_id"] not in identifiers:
            continue
        rows = publication_bindings(data, file["sha256"], file["url"])
        assert {row["table_index"] for row in rows} == {0, 1}
        assert cohorts_for("Printed 2025", {row["scope"] for row in rows}) == (["K71"], [])
        assert publication_bindings(data, "0"*64, file["url"]) == []


def test_generic_earlier_cohorts_and_unbound_rows_supply_no_exact_cohort():
    data = manifest()
    file = next(row for row in data["files"] if row["drive_id"] == "10zog4q-v_5cKsmcRCcFwLJXFU5tkTF6B")
    rows = publication_bindings(data, file["sha256"], file["url"])
    assert cohorts_for("", {row["scope"] for row in rows}) == ([], [])
    altered = deepcopy(data)
    for row in altered["rows"]:
        row["publication_sha256"] = "0"*64
    assert publication_bindings(altered, file["sha256"], file["url"]) == []
