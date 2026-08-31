import pytest
from app.core.agents.domain_expert import DomainExpert

@pytest.mark.asyncio
async def test_domain_expert_initialization():
    expert = DomainExpert()
    assert expert is not None
