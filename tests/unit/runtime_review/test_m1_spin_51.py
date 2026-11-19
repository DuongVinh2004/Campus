import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
from m1_affinity_20261011_41 import CPU as BaselineCPU
from m1_spin_policy_20261011_51 import CPU


def test_only_bounded_active_spin_policy_changes():
    before, after = dict(BaselineCPU.CONFIG), dict(CPU.CONFIG)
    changed = {k: v for k, v in after.items() if before.get(k) != v}
    assert changed == {b"session.intra_op.allow_spinning": b"1", b"session.intra_op.spin_duration_us": b"1000", b"session.force_spinning_stop": b"1"}
    assert after[b"session.inter_op.allow_spinning"] == b"0"
    assert after[b"session.intra_op_thread_affinities"] == b"3;5;7"
    assert after[b"session.dynamic_block_base"] == b"4"
    assert CPU.ALLOWED == BaselineCPU.ALLOWED
