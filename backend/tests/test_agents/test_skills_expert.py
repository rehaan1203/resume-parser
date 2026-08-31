import pytest
from app.core.agents.skills_expert import SkillsExpert

@pytest.mark.asyncio
async def test_skills_expert_initialization():
    expert = SkillsExpert()
    assert expert is not None
