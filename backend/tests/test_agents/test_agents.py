import pytest
from app.core.agents.writer_agent import WriterAgent
from app.core.agents.critic_agent import CriticAgent
from app.core.agents.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_writer_agent_initialization():
    agent = WriterAgent()
    assert agent is not None

@pytest.mark.asyncio
async def test_critic_agent_initialization():
    agent = CriticAgent()
    assert agent is not None

@pytest.mark.asyncio
async def test_orchestrator_initialization():
    orchestrator = Orchestrator()
    assert orchestrator is not None
