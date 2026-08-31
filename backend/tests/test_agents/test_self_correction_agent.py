import pytest
from app.core.agents.self_correction_agent import SelfCorrectionAgent

@pytest.mark.asyncio
async def test_correction_applied_initialization():
    """Test self-correction agent initializes."""
    agent = SelfCorrectionAgent()
    assert agent is not None
