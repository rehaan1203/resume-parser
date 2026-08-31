import pytest
from app.core.agents.multi_agent_orchestrator import MultiAgentOrchestrator

@pytest.mark.asyncio
async def test_multi_agent_orchestrator_initialization():
    orchestrator = MultiAgentOrchestrator()
    assert orchestrator is not None
