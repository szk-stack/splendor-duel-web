"""拿筹码规则测试。"""
import pytest

from engine.types import InvalidAction


def pick(game, n=1, prefer=None):
    """选 n 个相邻非金币格。prefer: 优先挑选的颜色。"""
    cells = [i for i, t in enumerate(game.state.board)
             if t != "gold" and (prefer is None or t == prefer)]
    return cells[:n]


def test_take_one(game):
    cell = pick(game)[0]
    color = game.state.board[cell]
    game.step(0, {"kind": "take_tokens", "cells": [cell]})
    s = game.state
    assert s.board[cell] is None
    assert s.players[0].tokens[color] == 1
    # 手牌 1 <= 10，直接换人
    assert s.current == 1


def test_take_two_adjacent(game):
    cells = pick(game, 2)
    a, b = cells
    dr = abs(a // 5 - b // 5)
    dc = abs(a % 5 - b % 5)
    assert max(dr, dc) == 1  # 相邻
    game.step(0, {"kind": "take_tokens", "cells": [a, b]})
    assert game.state.current == 1


def test_take_three_same_color_gives_privilege(game):
    # 控制棋盘：0/1/2 三格放红宝石（成一直线）
    s = game.state
    s.board[0] = s.board[1] = s.board[2] = "red"
    opp = s.players[1].privileges
    game.step(0, {"kind": "take_tokens", "cells": [0, 1, 2]})
    assert s.players[1].privileges == opp + 1
    assert s.players[0].tokens["red"] == 3


def test_cannot_take_gold(game):
    gold = [i for i, t in enumerate(game.state.board) if t == "gold"][0]
    with pytest.raises(InvalidAction) as e:
        game.step(0, {"kind": "take_tokens", "cells": [gold]})
    assert e.value.code == "ILLEGAL_ACTION"


def test_cannot_take_not_aligned(game):
    cells = pick(game, 2)
    a, b = cells
    if abs(a // 5 - b // 5) + abs(a % 5 - b % 5) == 0:
        pass
    # 找一个不成相邻的格
    far = next(i for i in range(25) if i != a and i != b
               and abs(i // 5 - a // 5) > 1 or abs(i % 5 - a % 5) > 1)
    with pytest.raises(InvalidAction) as e:
        game.step(0, {"kind": "take_tokens", "cells": [a, far]})
    assert e.value.code == "NOT_ALIGNED"


def test_take_more_than_3_rejected(game):
    cells = pick(game, 3)
    with pytest.raises(InvalidAction):
        game.step(0, {"kind": "take_tokens", "cells": cells + [cells[0]]})


def test_take_unsorted_cells_accepted(game):
    """乱序提交同一直线的 3 格（10/15/20 竖线）应通过——与点击顺序无关。"""
    s = game.state
    s.board[10] = s.board[15] = s.board[20] = "red"
    # 故意乱序：先两端后中间
    game.step(0, {"kind": "take_tokens", "cells": [15, 20, 10]})
    assert s.players[0].tokens["red"] == 3
    assert s.board[10] is None and s.board[15] is None and s.board[20] is None


def test_take_gap_in_line_rejected(game):
    """隔一格的"伪直线"（0 和 2，中间 1 是空的/未选）仍被拒。"""
    s = game.state
    s.board[0] = s.board[1] = s.board[2] = "red"
    with pytest.raises(InvalidAction) as e:
        game.step(0, {"kind": "take_tokens", "cells": [0, 2]})
    assert e.value.code == "NOT_ALIGNED"


def test_take_two_pearls_gives_privilege(game):
    # 找两颗珍珠
    s = game.state
    pearl_cells = [i for i, t in enumerate(s.board) if t == "pearl"]
    if len(pearl_cells) == 2 and max(abs(pearl_cells[0] // 5 - pearl_cells[1] // 5),
                                     abs(pearl_cells[0] % 5 - pearl_cells[1] % 5)) == 1:
        opp = s.players[1].privileges
        game.step(0, {"kind": "take_tokens", "cells": pearl_cells})
        assert s.players[1].privileges == opp + 1
