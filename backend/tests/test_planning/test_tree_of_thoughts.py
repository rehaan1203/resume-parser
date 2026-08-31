import pytest
from app.core.planning.tree_of_thoughts import TreeOfThoughts

@pytest.mark.asyncio
async def test_tree_of_thoughts_initialization():
    tot = TreeOfThoughts()
    assert tot is not None
