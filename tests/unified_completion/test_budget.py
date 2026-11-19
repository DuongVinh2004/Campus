import pytest
from campus247.application.single_agent.resources import AgentStop, BoundedGateway, RunResources
from campus247.application.multi_agent.contracts import MultiAgentPolicy
from campus247.ports.llm import LlmRequest


@pytest.mark.asyncio
async def test_reservation_exhausts_deadline_before_dispatch_without_uncertainty():
    calls, phases = [], []
    class Gateway:
        async def generate(self, request):
            calls.append(request)
            pytest.fail('expired reservation dispatched')
    resources = RunResources(MultiAgentPolicy(deadline_seconds=.05))
    def pending(phase):
        phases.append(phase)
        if phase == 'model': resources.expires = resources.started - 1
    gateway = BoundedGateway(Gateway(), resources, pending=pending)
    request = LlmRequest(request_id='fixture', route_id='fixture', model_profile='default',
        system_instructions='fixture', input_items=(), max_output_tokens=10, deadline_ms=100)
    with pytest.raises(AgentStop, match='DEADLINE_EXCEEDED'): await gateway.generate(request)
    assert calls == [] and phases == ['model', None]
    assert resources.usage['model_calls'] == 0 and resources.usage['usage_complete']
