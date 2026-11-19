"""The new local scope cannot alter old rows or grant further questions/messages."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
import m1_chat_journal_20261011_33 as journal


def package():
    before = journal.original()
    after = copy.deepcopy(before)
    conv = copy.deepcopy(before["conversation"][-1])
    conv.update(id="019a0000-0033-7000-8000-000000000001", version=1)
    after["conversation"].append(conv)
    return before, after


@pytest.mark.xfail(strict=False, reason="historical acceptance check: compares against the retained paid-call ledger and chat journal as they were at acceptance time; both have grown since, so it cannot match again without rewriting retained evidence (audit 2026-11-03, owner-approved)")
def test_composed_guard_retains_eight_historical_reservations_exactly():
    rows, before, last = journal.journal()
    assert rows == [] and last == journal.OLD_LAST_SHA
    assert len(before["conversation"]) == 2 and len(before["message"]) == 12


def test_exact_one_owned_conversation_scope():
    before, after = package()
    journal.validate(after, before)
    after["conversation"][-1]["owner_user_id"] = "foreign-actor"
    with pytest.raises(AssertionError):
        journal.validate(after, before)


@pytest.mark.parametrize("table", ["conversation", "message"])
def test_old_rows_cannot_be_changed(table):
    before, after = package()
    after[table][0]["id"] = "replacement"
    with pytest.raises((AssertionError, KeyError)):
        journal.validate(after, before)


def test_only_exact_first_question_permitted():
    before, after = package()
    message = copy.deepcopy(before["message"][0])
    message.update(id="019a0000-0033-7000-8000-000000000002", conversation_id=after["conversation"][-1]["id"],
        sequence_no=1, sender_type="USER", sender_user_id=journal.ACTOR, content_redacted=journal.QUESTIONS[0], citations=[])
    after["message"].append(message)
    after["conversation"][-1]["version"] = 2
    journal.validate(after,before)
    message["content_redacted"] = "unapproved different question"
    with pytest.raises(AssertionError):
        journal.validate(after,before)
