import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"infra/local/rag-fixture"))
import m1_chat_journal_20261011_34 as journal
from m1_cpu_20261011_34 import CPU,RestrictedCPU


def additions(count):
    before=journal.original(); after=copy.deepcopy(before)
    template=next(m for m in before["message"] if m["conversation_id"]==journal.CONVERSATION)
    for i in range(count):
        row=copy.deepcopy(template)
        row.update(id=f"019a0000-0034-7000-8000-{i+1:012}",sequence_no=i+2,
            sender_type="USER" if i%2==0 else "ASSISTANT",sender_user_id=journal.ACTOR if i%2==0 else None,
            content_redacted=journal.QUESTIONS[i//2] if i%2==0 else "synthetic answer",citations=[])
        after["message"].append(row)
    next(c for c in after["conversation"] if c["id"]==journal.CONVERSATION)["version"]=2+count
    return before,after


def test_same_conversation_seven_total_including_failed_user():
    before,after=additions(6)
    journal.validate(after,before)
    assert len(after["message"])-12==7


@pytest.mark.parametrize("table",["conversation","message"])
def test_historical_rows_and_failed_user_immutable(table):
    before,after=additions(2)
    if table=="message":
        after[table][12]["content_redacted"]="overwrite failure"
    else:
        after[table][0]["status"]="CLOSED"
    with pytest.raises(AssertionError):journal.validate(after,before)


def test_wrong_follow_up_rejected():
    before,after=additions(3);after["message"][-1]["content_redacted"]=journal.QUESTIONS[2]
    with pytest.raises(AssertionError):journal.validate(after,before)


def test_extra_conversation_rejected():
    before,after=additions(0);after["conversation"].append(copy.deepcopy(after["conversation"][-1]))
    with pytest.raises(AssertionError):journal.validate(after,before)


def test_dynamic_config_preserves_no_spinning(monkeypatch):
    calls=[]
    monkeypatch.setattr(RestrictedCPU,"status",lambda self,name,args,*values:calls.append((name,values)))
    engine=object.__new__(CPU);engine.status("CreateSession",[],None,"model",123,None)
    config={v[1]:v[2] for name,v in calls if name=="AddSessionConfigEntry"}
    assert config==CPU.CONFIG and config[b"session.dynamic_block_base"]==b"4"


@pytest.mark.parametrize("key,value",[(b"unreviewed",b"4"),(b"session.dynamic_block_base",b"0"),(b"session.intra_op.allow_spinning",b"1")])
def test_unreviewed_runtime_config_rejected(key,value):
    with pytest.raises(AssertionError):object.__new__(CPU).status("AddSessionConfigEntry",[],123,key,value)
