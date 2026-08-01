"""共享 fixture：固定种子的真实数据对局。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.data import CardLibrary  # noqa: E402
from engine.game import Game  # noqa: E402


@pytest.fixture
def library():
    return CardLibrary()


@pytest.fixture
def game(library):
    """固定种子 42 的一局（真实数据）。"""
    return Game(library, seed=42, nicknames=("Alice", "Bob"))
