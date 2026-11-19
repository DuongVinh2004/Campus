import json

import pytest

from model_usage_accounting import accounting_continuation, exceeds, native_snapshot


def test_uncapped_continuation_preserves_usage_and_crosses_old_caps():
    previous={"counts":{"http":20000,"inference":10000,"tokens":5000000}}
    counts,caps=accounting_continuation(previous)
    assert counts==previous["counts"] and counts is not previous["counts"]
    assert all(cap is None for cap in caps.values())
    assert not any(exceeds(counts[k]+1,caps[k]) for k in counts)
    assert exceeds(10001,10000)


def test_snapshot_orders_six_digit_ordinals_and_rejects_regression(retained_directory):
    def record(ordinal,http,tokens):
        value={"counts":{"inference":ordinal,"http":http,"tokens":tokens},"caps":{"http":None,"inference":None,"tokens":None}}
        (retained_directory/f"native-{ordinal:05d}-reservation.json").write_text(json.dumps(value),encoding="utf-8")
    record(99999,150000,7000000)
    record(100000,150001,7000001)
    assert native_snapshot(retained_directory,lambda p:p)["counts"]["inference"]==100000
    record(100001,150002,6000000)
    with pytest.raises(ValueError,match="regressed"):
        native_snapshot(retained_directory,lambda p:p)
