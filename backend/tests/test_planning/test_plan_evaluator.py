import pytest
from app.core.planning.plan_evaluator import PlanEvaluator

@pytest.mark.asyncio
async def test_plan_evaluator_initialization():
    evaluator = PlanEvaluator()
    assert evaluator is not None
