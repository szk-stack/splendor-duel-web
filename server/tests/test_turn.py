"""回合流转、弃牌、特权、补充棋盘、额外回合测试。"""
import pytest

from engine.types import InvalidAction


def first_non_gold(game, slot=None):
    return [i for i, t in enumerate(game.state.board) if t != "gold"][0]


def test_turn_switches(game):
    c = first_non_gold(game)
    game.step(0, {"kind": "take_tokens", "cells": [c]})
    assert game.state.current == 1
    assert game.state.turn == 1
    # 轮不到 0 号行动
    with pytest.raises(InvalidAction) as e:
        game.step(0, {"kind": "take_tokens", "cells": [c]})
    assert e.value.code == "NOT_YOUR_TURN"


def test_discard_to_10(game):
    s = game.state
    # 给 12 个筹码，拿 1 个 -> 13 > 10 必须弃 3
    give_hand(s.players[0], white=12)
    non_gold = [i for i, t in enumerate(s.board) if t == "red"][0]
    game.step(0, {"kind": "take_tokens", "cells": [non_gold]})
    assert s.phase.value == "discard"
    # 弃错数量被拒
    with pytest.raises(InvalidAction):
        game.step(0, {"kind": "discard", "colors": {"white": 2}})
    # 正确弃牌 -> 换人
    game.step(0, {"kind": "discard", "colors": {"white": 3}})
    assert s.players[0].total_tokens() == 10
    assert s.current == 1 and s.phase.value == "optional"


def give_hand(p, **tokens):
    for c, n in tokens.items():
        p.tokens[c] += n


def test_privilege_limited_to_one_per_turn(game):
    """特权每回合最多用 1 次（+1 次补充棋盘 = 2 个可选行动）。"""
    s = game.state
    # 0 号先走，轮到 1 号（有 1 起始特权）
    game.step(0, {"kind": "take_tokens", "cells": [first_non_gold(game)]})
    p1 = s.players[1]
    p1.privileges = 3  # 多给几个，验证仍只限 1 次行动
    s.privilege_pool = 0
    cell = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    game.step(1, {"kind": "use_privilege", "cells": [cell]})
    assert p1.privileges == 2
    # 同回合第二次行动被拒
    cell2 = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    with pytest.raises(InvalidAction) as e:
        game.step(1, {"kind": "use_privilege", "cells": [cell2]})
    assert e.value.code == "PRIVILEGE_USED"
    # 下回合恢复
    game.step(1, {"kind": "take_tokens", "cells": [cell2]})
    take = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    game.step(0, {"kind": "take_tokens", "cells": [take]})
    assert s.current == 1
    cell3 = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    game.step(1, {"kind": "use_privilege", "cells": [cell3]})
    assert p1.privileges == 1


def test_privilege_multi_spend(game):
    """一次使用特权可放回多个（1~3），拿取对应数量筹码。"""
    s = game.state
    game.step(0, {"kind": "take_tokens", "cells": [first_non_gold(game)]})
    p1 = s.players[1]
    p1.privileges = 3
    s.privilege_pool = 0
    cells = [i for i, t in enumerate(s.board) if t not in (None, "gold")][:3]
    game.step(1, {"kind": "use_privilege", "cells": cells})
    assert p1.privileges == 0
    assert s.privilege_pool == 3
    assert p1.total_tokens() == 3
    assert all(s.board[c] is None for c in cells)
    # 超过持有数被拒（需先结束本回合，避免先被 PRIVILEGE_USED 拦截）
    take = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    game.step(1, {"kind": "take_tokens", "cells": [take]})
    take2 = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    game.step(0, {"kind": "take_tokens", "cells": [take2]})
    assert s.current == 1
    p1.privileges = 1
    cells2 = [i for i, t in enumerate(s.board) if t not in (None, "gold")][:2]
    with pytest.raises(InvalidAction) as e:
        game.step(1, {"kind": "use_privilege", "cells": cells2})
    assert e.value.code == "ILLEGAL_ACTION"


def test_use_privilege(game):
    s = game.state
    # 先手没特权不能使用
    with pytest.raises(InvalidAction) as e:
        game.step(0, {"kind": "use_privilege", "cells": [first_non_gold(game)]})
    assert e.value.code == "NO_PRIVILEGE"
    # 换后手（有 1 特权）使用
    game.step(0, {"kind": "take_tokens", "cells": [first_non_gold(game)]})
    # 选一个仍占位的非金币格（刚才 0 号拿走的格已空）
    cell = next(i for i, t in enumerate(s.board) if t not in (None, "gold"))
    color = s.board[cell]
    game.step(1, {"kind": "use_privilege", "cells": [cell]})
    p1 = s.players[1]
    assert p1.privileges == 0
    assert p1.tokens[color] == 1
    assert s.privilege_pool == 3  # 放回图板上方
    # 仍是 1 号玩家的回合（可选行动不结束回合）
    assert s.current == 1
    # 特权已用，再用被拒
    with pytest.raises(InvalidAction):
        game.step(1, {"kind": "use_privilege", "cells": [cell]})


def test_fill_board_gives_opponent_privilege(game):
    s = game.state
    # 先清出 3 个空位（模拟筹码被取走）
    s.board[0] = s.board[1] = s.board[2] = None
    s.bag["white"] = 5
    game.step(0, {"kind": "fill_board"})
    assert s.players[1].privileges == 2  # 对手获 1 特权
    assert s.current == 0  # 仍是本回合
    # 3 个空位被填满（布袋剩余 2）
    assert all(s.board[i] for i in (0, 1, 2))
    assert s.bag["white"] == 2
    # 补充后再补充被拒
    with pytest.raises(InvalidAction):
        game.step(0, {"kind": "fill_board"})


def test_replay_extra_turn(library, game):
    """买 replay 卡后同一玩家再行动一回合。"""
    s = game.state
    loc = None
    for tier, slots in s.pyramid.items():
        if "carte_5" in slots:
            loc = (tier, slots.index("carte_5"))
            break
    if loc is None:
        pytest.skip("carte_5 未在展示区")
    tier, slot = loc
    cost = game.library.card("carte_5")["cost"]  # 白2 黑2 珍珠1
    give_hand(s.players[0], **{c: n for c, n in cost.items() if n})
    payment = {c: {"tokens": n, "gold": 0} for c, n in cost.items() if n}
    game.step(0, {"kind": "buy", "source": "pyramid", "tier": tier, "slot": slot,
                  "payment": payment})
    assert s.current == 0  # replay：仍是 0 号
    assert s.turn == 0  # 回合计数不变
    # 再行动一次，正常换人
    game.step(0, {"kind": "take_tokens", "cells": [first_non_gold(game)]})
    assert s.current == 1
    assert s.turn == 1


def test_force_fill_when_no_mandatory(game):
    """无任何强制行动可行时（无筹码、无金币、无可买），必须先补充棋盘。"""
    s = game.state
    s.board = [None] * 25  # 全空：无筹码可拿、无金币可保留
    s.bag = {"white": 3, "red": 2, "blue": 0, "green": 0, "black": 0,
             "pearl": 0, "gold": 0}
    legal = game.legal_actions(0)
    assert [a["kind"] for a in legal["actions"]] == ["force_fill"]
    # 拿取行动被拒
    with pytest.raises(InvalidAction):
        game.step(0, {"kind": "take_tokens", "cells": [0]})
    # 补充后恢复
    game.step(0, {"kind": "fill_board"})
    kinds = [a["kind"] for a in game.legal_actions(0)["actions"]]
    assert "take_tokens" in kinds
