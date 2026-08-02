"""AI 玩家测试：提示词/解析/兜底/回合循环（mock 大模型，不发真实请求）。"""
import asyncio
import json

import pytest

from engine.data import CardLibrary
from engine.game import Game
from app import ai_player
from app.ai_player import build_messages, parse_action, random_legal_action, take_turn


# ---------------------------------------------------------------- 提示词与解析

def test_build_messages_includes_state_legal_and_error():
    board = ["white"] * 25
    msgs = build_messages({"board": board}, {"actions": [{"kind": "fill_board"}]}, "E1: 出错")
    assert msgs[0]["role"] == "system"
    assert "璀璨宝石" in msgs[0]["content"]
    body = msgs[1]["content"]
    assert '"board"' in body and "fill_board" in body and "E1: 出错" in body
    assert "0:白" in body  # ASCII 棋盘渲染


def test_parse_action_plain_json():
    assert parse_action('{"kind": "take_tokens", "cells": [0]}') == {
        "kind": "take_tokens", "cells": [0]}


def test_parse_action_markdown_fence():
    text = '```json\n{"kind": "fill_board"}\n```'
    assert parse_action(text) == {"kind": "fill_board"}


def test_parse_action_with_extra_text():
    text = '我选择拿筹码：{"kind": "take_tokens", "cells": [3]} 完毕'
    assert parse_action(text) == {"kind": "take_tokens", "cells": [3]}


def test_parse_action_no_json_raises():
    with pytest.raises(ValueError):
        parse_action("没有任何 JSON 的回复")


# ---------------------------------------------------------------- 随机兜底

def test_random_legal_take_tokens():
    legal = {"actions": [{"kind": "take_tokens", "cells": [0, 1, 5, 6]}]}
    a = random_legal_action(legal)
    assert a["kind"] == "take_tokens" and len(a["cells"]) == 1
    assert a["cells"][0] in [0, 1, 5, 6]


def test_random_legal_reserve_pyramid():
    legal = {"actions": [{"kind": "reserve", "gold_cells": [2, 3],
                          "pyramid": {"1": [0, 1], "2": [0]}, "decks": []}]}
    a = random_legal_action(legal)
    assert a["kind"] == "reserve"
    assert a["source"] == "pyramid" and a["tier"] in (1, 2)
    assert a["gold_cell"] in (2, 3)


def test_random_legal_reserve_deck():
    legal = {"actions": [{"kind": "reserve", "gold_cells": [2],
                          "pyramid": {}, "decks": [3]}]}
    a = random_legal_action(legal)
    assert a == {"kind": "reserve", "source": "deck", "tier": 3, "gold_cell": 2}


def test_random_legal_fill_board():
    legal = {"actions": [{"kind": "fill_board"}]}
    assert random_legal_action(legal) == {"kind": "fill_board"}


def test_random_legal_none():
    assert random_legal_action({"actions": []}) is None


# ---------------------------------------------------------------- 行动规范化

def test_normalize_take_tokens_filters_illegal_cells(library):
    from app.ai_player import normalize_action
    from app.rooms import PlayerSession, Room
    room = Room(code="X", ai_mode=True)
    room.players[1] = PlayerSession(slot=1, token="AI", nickname="AI", is_ai=True)
    room.game = Game(library, seed=3)
    room.game.state.players[1].is_ai = True
    room.game.state.current = 1  # AI 回合
    legal = room.game.legal_actions(1)
    # 模型输出含金币格/不存在的格 → 过滤为合法单格
    gold = next(i for i, t in enumerate(room.game.state.board) if t == "gold")
    a = normalize_action({"kind": "take_tokens", "cells": [gold, 999, 5]},
                         room.game, legal)
    assert a["kind"] == "take_tokens"
    assert len(a["cells"]) == 1
    assert a["cells"][0] != gold  # 过滤掉了金币格


def test_normalize_buy_generates_payment(library):
    """模型输出买卡意图 → 自动生成合法支付明细 → 引擎可执行。"""
    from app.ai_player import normalize_action
    from app.rooms import PlayerSession, Room
    room = Room(code="X", ai_mode=True)
    room.players[1] = PlayerSession(slot=1, token="AI", nickname="AI", is_ai=True)
    room.game = Game(library, seed=3)
    room.game.state.players[1].is_ai = True
    room.game.state.current = 1  # AI 回合
    # 给 AI 充足筹码 + 把一张便宜的卡放进展示区
    p = room.game.state.players[1]
    p.tokens = {c: 6 for c in p.tokens}
    room.game.state.pyramid[1][0] = "carte_6"  # 4 色各 1 的便宜卡
    legal = room.game.legal_actions(1)
    buy = next((a for a in legal["actions"] if a["kind"] == "buy"), None)
    assert buy, "应存在可负担的 buy option"
    opt = buy["options"][0]
    a = normalize_action({"kind": "buy", "card_id": opt["card"]["id"]}, room.game, legal)
    assert a["kind"] == "buy"
    # 支付明细覆盖有效费用
    events = room.game.step(1, a)
    assert events and any(e["type"] == "card_bought" for e in events)


# ---------------------------------------------------------------- 回合循环

class FakeChat:
    """按次数依次返回预设回复的 mock。"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    async def __call__(self, messages, **kw):
        self.calls += 1
        if not self.replies:
            raise ai_player.ai_client.AIError("mock 耗尽")
        return self.replies.pop(0)


def make_ai_room(library, seed=42):
    """构造 AI 房间：slot 1 是 AI，轮到 AI 行动（固定 0 号先手走一步）。"""
    from app.rooms import PlayerSession, Room
    room = Room(code="AITEST", ai_mode=True)
    room.players[0] = PlayerSession(slot=0, token="t0", nickname="真人", ws=object())
    room.players[1] = PlayerSession(slot=1, token="AI", nickname="AI", is_ai=True)
    room.game = Game(library, seed=seed, nicknames=("真人", "AI"))
    room.game.state.players[1].is_ai = True
    room.game.state.current = 0  # 固定真人先手（测试确定性）
    room.game.state.players[0].privileges = 0
    room.game.state.players[1].privileges = 1
    room.game.state.privilege_pool = 2
    # 真人先走一步，轮到 AI
    cell = next(i for i, t in enumerate(room.game.state.board) if t != "gold")
    room.game.step(0, {"kind": "take_tokens", "cells": [cell]})
    assert room.game.state.current == 1
    return room


def run(room, expect_game=None):
    """运行 take_turn；expect_game 模拟 main.py 的广播丢弃（对局替换时旧事件作废）。"""
    events = []

    async def broadcast(ev, le=None):
        if expect_game is not None and room.game is not expect_game:
            return  # 对局已替换，旧任务事件丢弃
        events.append(ev)

    asyncio.run(take_turn(room, broadcast))
    return events


@pytest.fixture
def library():
    return CardLibrary()


def _free_cell(game):
    """取一个当前可拿的非空非金币格。"""
    return next(i for i, t in enumerate(game.state.board) if t not in (None, "gold"))


def test_take_turn_valid_action(library, monkeypatch):
    room = make_ai_room(library)
    cell = _free_cell(room.game)
    fake = FakeChat([json.dumps({"kind": "take_tokens", "cells": [cell]})])
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    assert fake.calls == 1
    assert any(e[-1]["type"] == "turn_changed" for e in events)
    assert room.game.state.current == 0  # 轮到真人
    assert not room.ai_busy


def test_take_turn_invalid_then_valid(library, monkeypatch):
    """第一次返回非法行动（含金币格）被拒，带错误重试后成功。"""
    room = make_ai_room(library)
    gold = next(i for i, t in enumerate(room.game.state.board) if t == "gold")
    cell = _free_cell(room.game)
    fake = FakeChat([
        json.dumps({"kind": "take_tokens", "cells": [gold]}),  # 非法
        json.dumps({"kind": "take_tokens", "cells": [cell]}),  # 合法
    ])
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    assert fake.calls == 2
    assert room.game.state.current == 0


def test_take_turn_all_invalid_falls_back(library, monkeypatch):
    """全部非法 → 随机合法行动兜底，对局不卡死。"""
    room = make_ai_room(library)
    gold = next(i for i, t in enumerate(room.game.state.board) if t == "gold")
    fake = FakeChat([json.dumps({"kind": "take_tokens", "cells": [gold]})] * 3)
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    assert fake.calls == 3  # 首次 + MAX_RETRY 次重试
    assert room.game.state.current == 0  # 兜底行动后轮到真人
    assert events


def test_take_turn_api_failure_falls_back(library, monkeypatch):
    room = make_ai_room(library)
    fake = FakeChat([])  # 立即抛 AIError
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    assert room.game.state.current == 0  # 兜底成功


def test_parse_action_unclosed_fence():
    """未闭合的 markdown 代码块不抛 IndexError。"""
    assert parse_action('```json\n{"kind": "fill_board"}') == {"kind": "fill_board"}


def test_random_legal_discard():
    """弃牌阶段兜底：构造恰好弃 over 个的明细。"""
    legal = {"phase": "discard", "discard": {"over": 3, "hand": {"white": 2, "red": 5}}}
    a = random_legal_action(legal)
    assert a["kind"] == "discard"
    assert sum(a["colors"].values()) == 3
    assert a["colors"]["white"] == 2 and a["colors"]["red"] == 1


def test_random_legal_force_fill():
    legal = {"actions": [{"kind": "force_fill"}]}
    assert random_legal_action(legal) == {"kind": "fill_board"}


def test_take_turn_discard_fallback(library, monkeypatch):
    """AI 手牌超限进入弃牌阶段：模型输出垃圾 → 兜底弃牌成功，对局推进。"""
    from app.rooms import PlayerSession, Room
    room = Room(code="DISC", ai_mode=True)
    room.players[0] = PlayerSession(slot=0, token="t0", nickname="真人", ws=object())
    room.players[1] = PlayerSession(slot=1, token="AI1", nickname="AI", is_ai=True)
    room.game = Game(library, seed=7)
    room.game.state.players[1].is_ai = True
    room.game.state.current = 0
    room.game.state.players[1].privileges = 1
    room.game.state.privilege_pool = 2
    # 真人先手走一步，轮到 AI；给 AI 塞满手牌（>10 触发弃牌）
    cell = next(i for i, t in enumerate(room.game.state.board) if t != "gold")
    room.game.step(0, {"kind": "take_tokens", "cells": [cell]})
    p = room.game.state.players[1]
    p.tokens = {"white": 5, "blue": 4, "green": 0, "red": 0, "black": 0,
                "pearl": 0, "gold": 3}
    # 模型持续输出垃圾（无法解析）
    fake = FakeChat(['这不是 JSON'] * 3)
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    # 兜底弃牌后轮到真人
    assert room.game.state.current == 0
    assert room.game.state.players[1].total_tokens() == 10


class BlockingChat:
    """在 API 调用期间执行回调一次（模拟等待期间对局被替换），之后持续报错。"""

    def __init__(self, callback):
        self.callback = callback
        self.called = False
        self.replaced = False

    async def __call__(self, messages, **kw):
        self.called = True
        if not self.replaced:
            self.replaced = True
            self.callback()
        raise ai_player.ai_client.AIError("被替换")


def test_take_turn_stale_game_exits(library, monkeypatch):
    """API 等待期间对局被替换 → 过期 AI 任务检测后退出，不广播旧事件。"""
    from app.rooms import PlayerSession, Room
    room = Room(code="STALE", ai_mode=True)
    room.players[0] = PlayerSession(slot=0, token="t0", nickname="真人", ws=object())
    room.players[1] = PlayerSession(slot=1, token="AI1", nickname="AI", is_ai=True)
    room.game = Game(library, seed=7)
    room.game.state.players[1].is_ai = True
    room.game.state.current = 0
    room.game.state.players[1].privileges = 1
    room.game.state.privilege_pool = 2
    cell = next(i for i, t in enumerate(room.game.state.board) if t != "gold")
    room.game.step(0, {"kind": "take_tokens", "cells": [cell]})
    old_game = room.game

    def replace():
        # API 等待期间对局被替换（重开）
        room.game = Game(library, seed=8)
        room.game.state.players[1].is_ai = True

    fake = BlockingChat(replace)
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room, expect_game=old_game)
    assert fake.called  # 模型被调用（API 等待期间替换）
    assert events == []  # 旧任务事件被广播层丢弃
    # 旧对局停在 AI 回合（未被旧任务推进）；新对局独立（先手随机）
    assert old_game.state.current == 1
    assert room.game.state.current in (0, 1)


def test_normalize_buy_royal_steal_color(library):
    """皇家牌为偷取能力时，normalize 补全 royal_steal_color。"""
    from app.ai_player import normalize_action
    from app.rooms import PlayerSession, Room
    room = Room(code="R", ai_mode=True)
    room.players[1] = PlayerSession(slot=1, token="AI1", nickname="AI", is_ai=True)
    room.game = Game(library, seed=3)
    room.game.state.players[1].is_ai = True
    room.game.state.current = 1
    p = room.game.state.players[1]
    p.tokens = {c: 6 for c in p.tokens}
    # 构造：AI 已 2 皇冠，买 1 皇冠卡触发皇家牌；皇家池只留偷取牌
    p.crowns = 2
    steal_royal = next(r for r, d in library.royal_cards.items()
                       if d["capacity"] == "steal_opponent_pawn")
    room.game.state.royal_pool = [steal_royal]
    room.game.state.players[0].tokens["red"] = 2  # 对手有可偷筹码
    room.game.state.pyramid[1][0] = "carte_8"  # 1 皇冠
    legal = room.game.legal_actions(1)
    buy = next((a for a in legal["actions"] if a["kind"] == "buy"), None)
    assert buy, "应存在 buy option"
    opt = buy["options"][0]
    a = normalize_action({"kind": "buy", "card_id": opt["card"]["id"]}, room.game, legal)
    assert a["royal_choice"] == steal_royal
    assert a.get("royal_steal_color") == "red"
    events = room.game.step(1, a)  # 引擎应接受
    assert any(e["type"] == "royal_taken" for e in events)


def test_take_turn_not_ai_turn_returns(library, monkeypatch):
    """不是 AI 回合（轮到真人）→ 直接返回不调用模型。"""
    room = make_ai_room(library)
    room.game.step(1, {"kind": "take_tokens",
                       "cells": [next(i for i, t in enumerate(room.game.state.board)
                                      if t not in (None, "gold"))]})
    assert room.game.state.current == 0
    fake = FakeChat([])
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)
    events = run(room)
    assert fake.calls == 0
    assert events == []
