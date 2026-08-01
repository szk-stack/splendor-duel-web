"""购买卡牌规则测试。"""
import pytest

from engine.types import InvalidAction
from helpers import show, give_hand, pay_for, buy_displayed


def test_buy_with_bonus_reduction(game):
    """买 carte_8（黑3，红奖励1皇冠）：支付、皇冠、奖励、补牌、换人。"""
    s = game.state
    give_hand(s.players[0], black=3)
    game.step(0, buy_displayed(game, 0, "carte_8"))
    p = s.players[0]
    assert p.crowns == 1
    assert p.bought[-1]["bonus"] == "red"
    assert p.bonus()["red"] == 1
    assert p.tokens["black"] == 0
    assert s.bag["black"] == 3
    assert s.pyramid[1][0] is not None  # 展示区已补牌
    assert s.current == 1


def test_bonus_reduces_cost(game):
    """奖励减免：红奖励只减红色费用。先买 carte_8（红奖励），
    再买 carte_34（需红4+珍珠1）→ 红只需付 3。"""
    s = game.state
    give_hand(s.players[0], black=3, red=4, pearl=1)
    game.step(0, buy_displayed(game, 0, "carte_8"))  # 红奖励卡
    from helpers import take_one
    take_one(game, 1)  # 对手回合
    # 买 carte_34：红 4-1(奖励)=3
    show(game, "carte_34")
    game.step(0, {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
                  "payment": {"red": {"tokens": 3, "gold": 0},
                              "pearl": {"tokens": 1, "gold": 0}}})
    p = s.players[0]
    assert p.bought[-1]["id"] == "carte_34"
    assert p.tokens["red"] == 1  # 4(给) - 3(付)
    # 若红奖励未生效，付 3 红会被拒（PAYMENT_INSUFFICIENT）——上面已通过，说明减免生效


def test_pay_with_gold(game):
    """金币可充当任意颜色：carte_16 需蓝3，用蓝2+金1 购买。"""
    s = game.state
    give_hand(s.players[0], blue=2, gold=1)
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {"blue": {"tokens": 2, "gold": 1}}}
    show(game, "carte_16")
    game.step(0, action)
    p = s.players[0]
    assert p.bought[-1]["id"] == "carte_16"
    assert p.tokens["blue"] == 0 and p.tokens["gold"] == 0
    assert s.bag["gold"] == 1  # 花掉的金币回布袋


def test_payment_insufficient_rejected(game):
    show(game, "carte_16")
    give_hand(game.state.players[0], blue=3)  # 足够购买，但支付明细不足
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {"blue": {"tokens": 2, "gold": 0}}}
    with pytest.raises(InvalidAction) as e:
        game.step(0, action)
    assert e.value.code == "PAYMENT_INSUFFICIENT"


def test_payment_exceeding_hand_rejected(game):
    show(game, "carte_16")
    give_hand(game.state.players[0], blue=3)
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {"blue": {"tokens": 5, "gold": 0}}}
    with pytest.raises(InvalidAction) as e:
        game.step(0, action)
    assert e.value.code == "PAYMENT_EXCEEDS"


def test_buy_from_reserved(game):
    """先保留 carte_8，再从保留区购买。"""
    s = game.state
    show(game, "carte_8")
    gold_cell = [i for i, t in enumerate(s.board) if t == "gold"][0]
    game.step(0, {"kind": "reserve", "source": "pyramid", "tier": 1,
                  "slot": 0, "gold_cell": gold_cell})
    p = s.players[0]
    assert "carte_8" in p.reserved
    assert p.tokens["gold"] == 1
    assert s.board[gold_cell] is None
    assert s.current == 1  # 保留是强制行动，回合结束

    # 对手回合后再买
    from helpers import take_one
    take_one(game, 1)
    give_hand(p, black=3)
    action = {"kind": "buy", "source": "reserved", "card_id": "carte_8",
              "payment": pay_for(game, "carte_8")}
    game.step(0, action)
    assert "carte_8" not in p.reserved
    assert p.bought[-1]["id"] == "carte_8"


def test_joker_buy_requires_bonus_card(game):
    """百搭卡：无奖励卡不能买；有后须叠放并复制颜色。"""
    s = game.state
    # 先买 carte_8（红奖励）
    give_hand(s.players[0], black=3)
    game.step(0, buy_displayed(game, 0, "carte_8"))
    # 对手回合
    from helpers import take_one
    take_one(game, 1)

    # 买 joker 卡 carte_33（黑4+珍珠1）
    give_hand(s.players[0], black=4, pearl=1)
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {"black": {"tokens": 4, "gold": 0},
                          "pearl": {"tokens": 1, "gold": 0}}}
    show(game, "carte_33")
    # 不指定叠放目标 -> 拒绝
    with pytest.raises(InvalidAction):
        game.step(0, action)
    # 指定目标 carte_8 -> 成功，奖励复制为 red
    action["joker_target"] = "carte_8"
    game.step(0, action)
    entry = s.players[0].bought[-1]
    assert entry["id"] == "carte_33"
    assert entry["bonus"] == "red" and entry["stacked_on"] == "carte_8"
    assert s.players[0].bonus()["red"] == 2  # carte_8 + 复制的 joker


def test_joker_without_any_bonus_card_rejected(game):
    """没有奖励卡时购买百搭卡被拒（购买限制）。"""
    s = game.state
    give_hand(s.players[0], black=4, pearl=1)
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {"black": {"tokens": 4, "gold": 0},
                          "pearl": {"tokens": 1, "gold": 0}}}
    show(game, "carte_33")
    with pytest.raises(InvalidAction):
        game.step(0, action)


def test_cannot_buy_if_not_affordable(game):
    s = game.state
    action = {"kind": "buy", "source": "pyramid", "tier": 1, "slot": 0,
              "payment": {}}
    show(game, "carte_58")  # 蓝6+珍珠1，0 筹码买不起
    with pytest.raises(InvalidAction) as e:
        game.step(0, action)
    assert e.value.code == "NOT_AFFORDABLE"


def test_force_fill_when_no_mandatory(game):
    """棋盘完全无可用行动（无筹码、无金币、无可买）-> 强制补充。"""
    s = game.state
    s.board = [None] * 25
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
