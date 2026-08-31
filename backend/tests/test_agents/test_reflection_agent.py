import pytest
from app.core.agents.reflection_agent import ReflectionAgent

@pytest.mark.asyncio
async def test_root_cause_analysis_initialization():
    """Test reflection agent initializes."""
    agent = ReflectionAgent()
    assert agent is not None
