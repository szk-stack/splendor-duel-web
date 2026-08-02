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


def set_starter(game, slot=0):
    """测试辅助：固定先手（并同步起始特权），保证测试确定性。"""
    s = game.state
    s.current = slot
    second = 1 - slot
    s.players[slot].privileges = 0
    s.players[second].privileges = 1
    s.privilege_pool = 2
    return game


@pytest.fixture
def game(library):
    """固定种子 42 的一局（真实数据），固定 0 号先手。"""
    return set_starter(Game(library, seed=42, nicknames=("Alice", "Bob")), 0)
