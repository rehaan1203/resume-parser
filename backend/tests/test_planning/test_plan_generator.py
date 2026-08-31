import pytest
from app.core.planning.plan_generator import PlanGenerator

@pytest.mark.asyncio
async def test_plan_generator_initialization():
    generator = PlanGenerator()
    assert generator is not None
