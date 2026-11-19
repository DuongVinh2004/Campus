from dataclasses import replace

from campus247.agent import graph
from campus247.agent.state import Route, Terminal
from campus247.application.knowledge.question_scope import tuition_clarification


def test_operational_graph_never_executes_synthetic_schedule(monkeypatch):
    def personal_schedule(state, **kwargs):
        return replace(state,route=Route.PERSONAL_SCHEDULE)
    def forbidden(state):
        raise AssertionError("Synthetic schedule tool was executed")
    monkeypatch.setattr(graph,"route_intent_node",personal_schedule)
    monkeypatch.setattr(graph,"execute_read_tool_node",forbidden)
    result=graph.CampusAgentWorkflow(knowledge_only=True).run("Contract fixture: personal schedule")
    assert result.terminal==Terminal.ABSTAINED
    assert "OPERATIONAL_CAPABILITY_UNAVAILABLE" in result.errors
    assert "Giải tích" not in result.draft.text
    assert not result.tool_candidate


def test_tuition_requires_explicit_cohort_program_and_academic_year():
    value=tuition_clarification("học phí ngành công nghệ thông tin")
    assert all(term in value for term in ("khóa học","chương trình","năm học","phụ thu"))
    assert tuition_clarification("CNTT cử nhân chính quy K71 năm học 2026-2027 học phí mỗi tín chỉ?") is None
    assert tuition_clarification("hồ sơ miễn giảm học phí gồm những gì?") is None


def test_budget_unavailable_is_explained_after_safety_routing():
    import asyncio
    from campus247.agent.nodes.async_io import retrieve_evidence_node
    from campus247.agent.state import AgentState, NormalizedTurn
    from campus247.application.knowledge.platform_models import PlatformError
    from campus247.domain.shared.values import generate_uuid7
    async def search(query):
        raise PlatformError(503,"MODEL_BUDGET_UNAVAILABLE","Budget insufficient")
    state=AgentState(request=NormalizedTurn(generate_uuid7(),generate_uuid7(),generate_uuid7(),"Contract retrieval question"),route=Route.GROUNDED_FAQ)
    result=asyncio.run(retrieve_evidence_node(state,search_fn=search))
    assert result.terminal==Terminal.ABSTAINED
    assert "AI_MODEL_BUDGET_UNAVAILABLE" in result.errors
    assert "AI_RETRIEVAL_UNAVAILABLE" not in result.errors
    assert "ngân sách mô hình" in result.draft.text
