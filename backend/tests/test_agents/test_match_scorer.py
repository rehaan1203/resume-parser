import pytest
from app.core.agents.match_scorer import MatchScorer

@pytest.mark.asyncio
async def test_match_scorer_initialization():
    scorer = MatchScorer()
    assert scorer is not None
