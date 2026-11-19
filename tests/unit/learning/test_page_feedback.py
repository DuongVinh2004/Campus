from datetime import UTC, datetime, timedelta

import pytest
from campus247.application.learning.page_feedback import (
    LearningPageFeedback,
    feedback_timestamp,
)


@pytest.mark.parametrize(("size", "count", "band"), [
    (9, 5, None), (10, 0, None), (10, 4, None), (10, 5, "5-9"),
    (10, 9, "5-9"), (10, 10, "10-19"), (20, 19, "10-19"), (20, 20, "20+"),
])
def test_snapshot_uses_one_pre_cutoff_projection_even_when_worker_runs_late(size, count, band):
    now = datetime(2030, 1, 1, tzinfo=UTC)
    cutoff = now + timedelta(minutes=1)
    window = {"offering_id": "a", "session_id": "s", "closes_at": feedback_timestamp(cutoff)}
    state = {
        "sessions": {"s": {"id": "s", "offering_id": "a"}},
        "versions": {"v": {"processing_state": "READY", "publication_state": "PUBLISHED", "material_id": "m"}},
        "materials": {"m": {"id": "m", "visibility": "VISIBLE", "offering_id": "a"}},
        "links": {"s:m": {"offering_id": "a", "active": True}},
        "members": {
            str(i): {"actor_subject_id": str(i), "offering_id": "a", "role": "STUDENT", "status": "ACTIVE"}
            for i in range(size)
        },
        "page_feedback": {
            str(i): {"actor_subject_id": str(i), "session_id": "s", "version_id": "v", "page_no": 3, "status": "ACTIVE"}
            for i in range(count)
        },
        "feedback_windows": {"s": window},
    }
    use_case = LearningPageFeedback()
    use_case.capture_feedback_window(state, window, now)
    # Later events may affect the live record and the roster, never the cutoff projection.
    for row in state["page_feedback"].values():
        row["status"] = "WITHDRAWN"
    for member in state["members"].values():
        member["status"] = "INACTIVE"
    use_case.capture_feedback_window(state, window, cutoff)
    use_case.finalize_feedback_windows(state, cutoff + timedelta(hours=2))
    expected = [] if band is None else [{"version_id": "v", "page_no": 3, "band": band}]
    assert window["published_summary"] == expected
    use_case.finalize_feedback_windows(state, cutoff + timedelta(days=2))
    assert window["published_summary"] == expected
