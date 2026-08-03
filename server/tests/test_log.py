"""对局日志条目（build_log_entry）覆盖测试：8 种操作 + 4 种卡牌效果 + 4 种皇家效果 + 偷取分支。"""
import pytest

from engine.data import CardLibrary
from engine.game import Game
from app.game_log import build_log_entry


@pytest.fixture
def library():
    return CardLibrary()


def make_game(library, seed=11):
    g = Game(library, seed=seed)
    g.state.current = 0
    g.state.players[0].privileges = 0
    g.state.players[1].privileges = 1
    g.state.privilege_pool = 2
    return g


def _entry(library, game, action, board_before=None, slot=0, nickname="真人"):
    if board_before is None:
        board_before = list(game.state.board)
    return build_log_entry(action, board_before, game.state, library, slot, nickname)


def test_take_tokens_colors(library):
    g = make_game(library)
    board = list(g.state.board)
    # 造三个已知颜色的格
    board[0], board[1], board[2] = "red", "white", "white"
    e = _entry(library, g, {"kind": "take_tokens", "cells": [0, 1, 2]},
               board_before=board)
    assert e["type"] == "take_tokens"
    assert e["tokens"] == {"red": 1, "white": 2}


def test_use_privilege(library):
    g = make_game(library)
    board = list(g.state.board)
    board[5], board[6] = "blue", "blue"
    e = _entry(library, g, {"kind": "use_privilege", "cells": [5, 6]},
               board_before=board)
    assert e["type"] == "use_privilege"
    assert e["privileges_used"] == 2
    assert e["tokens"] == {"blue": 2}


def test_fill_board(library):
    g = make_game(library)
    e = _entry(library, g, {"kind": "fill_board"})
    assert e["type"] == "fill_board"


def test_reserve_card(library):
    g = make_game(library)
    g.state.current = 0
    g.state.players[0].reserved.append("carte_8")  # 保留区新增的卡
    e = _entry(library, g, {"kind": "reserve", "source": "pyramid",
                            "tier": 1, "slot": 0})
    assert e["type"] == "reserve"
    assert e["card"]["id"] == "carte_8"
    assert e["card"]["cost"]["black"] == 3


def test_discard(library):
    g = make_game(library)
    e = _entry(library, g, {"kind": "discard", "colors": {"white": 2, "red": 1}})
    assert e["type"] == "discard"
    assert e["tokens"] == {"white": 2, "red": 1}


def test_concede(library):
    g = make_game(library)
    e = _entry(library, g, {"kind": "concede"})
    assert e["type"] == "concede"


@pytest.mark.parametrize("card_id,capacity", [
    ("carte_5", "replay"),
    ("carte_9", "take_on_board"),
    ("carte_36", "take_priviledge"),
    ("carte_37", "steal_opponent_pawn"),
])
def test_buy_card_capacity_effects(library, card_id, capacity):
    """4 种卡牌能力效果。"""
    g = make_game(library)
    g.state.players[0].bought.append(
        {"id": card_id, "bonus": "red", "bonus_number": 1,
         "points": 0, "stacked_on": None, "crowns": 0, "capacity": capacity})
    action = {"kind": "buy", "card_id": card_id,
              "payment": {"red": {"tokens": 1, "gold": 0}}}
    if capacity == "steal_opponent_pawn":
        action["steal_color"] = "blue"
        g.state.players[1].tokens["blue"] = 2  # 对手有可偷筹码
    if capacity == "take_on_board":
        action["take_cell"] = 3
        g.state.board[3] = "red"  # 棋盘有奖励色
    e = _entry(library, g, action)
    assert e["type"] == "buy"
    assert e["card"]["id"] == card_id
    assert e["effects"], f"{card_id} 应有能力效果"
    if capacity == "replay":
        assert "额外回合" in e["effects"][0]
    if capacity == "take_priviledge":
        assert "特权" in e["effects"][0]
    if capacity == "steal_opponent_pawn":
        assert "偷取" in e["effects"][0] and "蓝" in e["effects"][0]
    if capacity == "take_on_board":
        assert "红" in e["effects"][0]


def test_steal_no_opponent_token_effect_not_applied(library):
    """对手无可偷筹码 → 如实记录"效果未生效"。"""
    g = make_game(library)
    g.state.players[0].bought.append(
        {"id": "carte_37", "bonus": "blue", "bonus_number": 1,
         "points": 0, "stacked_on": None, "crowns": 0, "capacity": "steal_opponent_pawn"})
    g.state.players[1].tokens = {c: 0 for c in g.state.players[1].tokens}
    action = {"kind": "buy", "card_id": "carte_37", "steal_color": "blue",
              "payment": {}}
    e = _entry(library, g, action)
    assert "未生效" in e["effects"][0]


def test_take_on_board_no_cell_effect_not_applied(library):
    """棋盘无奖励色格 → 效果未生效。"""
    g = make_game(library)
    g.state.players[0].bought.append(
        {"id": "carte_9", "bonus": "red", "bonus_number": 1,
         "points": 0, "stacked_on": None, "crowns": 0, "capacity": "take_on_board"})
    board = [None] * 25  # 棋盘无红
    action = {"kind": "buy", "card_id": "carte_9", "payment": {}}
    e = _entry(library, g, action, board_before=board)
    assert "未生效" in e["effects"][0]


def test_buy_royal_card_effects(library):
    """购买触发皇家牌：4 种皇家卡效果 + royal_index。"""
    g = make_game(library)
    g.state.players[0].crowns = 3
    g.state.players[0].royal_cards = []  # 获得第 1 张
    g.state.players[0].bought.append(
        {"id": "carte_8", "bonus": "red", "bonus_number": 1,
         "points": 0, "stacked_on": None, "crowns": 1, "capacity": None})
    action = {"kind": "buy", "card_id": "carte_8", "payment": {}}
    for rc, capacity in library.royal_cards.items():
        g.state.royal_pool = [rc]
        action["royal_choice"] = rc
        if capacity["capacity"] == "steal_opponent_pawn":
            action["royal_steal_color"] = "black"
            g.state.players[1].tokens["black"] = 1
        else:
            action.pop("royal_steal_color", None)
        e = _entry(library, g, action)
        assert e["royal_card"]["id"] == rc
        assert e["royal_index"] == 1
        royal_effects = e.get("effects") or []
        if capacity["capacity"] == "replay":
            assert any("额外回合" in x for x in royal_effects)
        elif capacity["capacity"] == "take_priviledge":
            assert any("特权" in x for x in royal_effects)
        elif capacity["capacity"] == "steal_opponent_pawn":
            assert any("偷取" in x and "黑" in x for x in royal_effects)
        else:
            assert e["effects"] is None or e["effects"] == []  # 无能力皇家牌


# ---------------------------------------------------------------- 文件日志（GameLogger）

def test_log_action_source_markers(tmp_path, monkeypatch):
    """log_action 文件日志：兜底🔴 / 规范化🟡（含意图降级⚠）/ 模型原样（无标记）。"""
    from app.game_log import GameLogger
    monkeypatch.setattr("app.game_log.LOG_DIR", tmp_path)
    log = GameLogger("TEST")
    player = {"tokens": {"red": 1}, "points": 0, "bought": [],
              "crowns": 0, "privileges": 0, "reserved": []}
    state = {"players": [dict(player), dict(player)]}
    try:
        log.log_action(1, "AI", {"kind": "concede"}, state,
                       source="fallback", reason="重试耗尽")
        log.log_action(1, "AI", {"kind": "concede"}, state,
                       source="normalized",
                       raw_action={"kind": "buy", "card_id": "carte_1"})
        log.log_action(1, "AI", {"kind": "concede"}, state,
                       source="normalized",
                       raw_action={"kind": "reserve", "pyramid": {"2": [0]}},
                       note="保留意图的牌位不可用，已随机选择一张明牌")
        log.log_action(1, "AI", {"kind": "concede"}, state)  # 默认 model：无标记
    finally:
        log.close()
    text = log.path.read_text(encoding="utf-8")
    assert "🔴【兜底】" in text and "重试耗尽" in text
    assert "🟡【规范化】" in text and "carte_1" in text
    assert "⚠️【意图降级】" in text and "牌位不可用" in text
    assert text.count("🔴") == 1 and text.count("🟡") == 2
