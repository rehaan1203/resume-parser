import pytest
from app.core.agents.roadmap_planner import RoadmapPlanner

@pytest.mark.asyncio
async def test_roadmap_planner_initialization():
    planner = RoadmapPlanner()
    assert planner is not None
