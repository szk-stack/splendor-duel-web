"""AI 房间集成测试：创建/开局/AI 回合自动执行（mock 大模型）。"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import ai_player, main
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def recv_until(ws, mtype, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        msg = ws.receive_json()
        if msg["type"] == mtype:
            return msg
    raise TimeoutError(f"未收到 {mtype}")


def wait_ai_done(ws, prev_turn, timeout=15):
    """等待 AI 完成行动（轮到真人且回合数前进）。"""
    end = time.time() + timeout
    while time.time() < end:
        msg = ws.receive_json()
        if msg["type"] == "state" and msg["state"]["current"] == 0 \
                and msg["state"]["turn"] > prev_turn:
            return msg
    raise TimeoutError("AI 回合未完成")


class FakeChat:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def __call__(self, messages, **kw):
        self.calls += 1
        return self.reply


def _free_cell(state):
    return next(i for i, t in enumerate(state["board"]) if t not in (None, "gold"))


def test_ai_room_full_flow(client, monkeypatch):
    """AI 房间：创建 → 真人连接即开局 → 真人行动 → AI 自动回合。"""
    # 用固定合法回复（先取一个真实合法格位，随种子变化）
    from engine.data import get_library
    probe = get_library()
    from engine.game import Game
    g = Game(probe, seed=1)
    free_cell = next(i for i, t in enumerate(g.state.board) if t not in (None, "gold"))
    fake = FakeChat(json.dumps({"kind": "take_tokens", "cells": [free_cell]}))
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)

    r = client.post("/api/rooms", json={"nickname": "真人", "ai": True})
    assert r.status_code == 200, r.text
    data = r.json()

    with client.websocket_connect(
            f"/ws?room={data['room_code']}&token={data['token']}") as ws:
        hello = recv_until(ws, "hello")
        assert hello["slot"] == 0
        # 真人连接即开局（无需等待对手）
        st = recv_until(ws, "state")
        assert st["started"] is True
        # AI 玩家标记
        assert st["state"]["players"][1]["is_ai"] is True
        assert st["state"]["players"][1]["nickname"] == "AI"
        # 真人先手
        assert st["state"]["current"] == 0

        # 真人行动（拿 1 个筹码）
        cell = _free_cell(st["state"])
        ws.send_json({"type": "action", "action": {"kind": "take_tokens", "cells": [cell]}})
        st2 = recv_until(ws, "state")
        assert st2["state"]["current"] == 1  # 轮到 AI

        # AI 自动回合（mock 回复固定拿筹码行动）
        st3 = wait_ai_done(ws, prev_turn=st2["state"]["turn"])
        assert st3["state"]["current"] == 0  # AI 完成后轮到真人
        assert fake.calls >= 1


def test_ai_room_join_rejected(client):
    """AI 房间不可被真人加入（slot 1 已被 AI 占用）。"""
    r = client.post("/api/rooms", json={"nickname": "真人", "ai": True})
    data = r.json()
    resp = client.post(f"/api/rooms/{data['room_code']}/join", json={"nickname": "路人"})
    assert resp.status_code == 409


def test_ai_token_not_constant(client):
    """AI 会话 token 必须是随机值（不可用常量 "AI" 劫持）。"""
    r = client.post("/api/rooms", json={"nickname": "真人", "ai": True})
    data = r.json()
    # 尝试用常量 "AI" 连接 → 认证失败关闭
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws?room={data['room_code']}&token=AI"):
            pass


def test_ai_room_rematch_keeps_ai_flag(client, monkeypatch):
    """AI 房间再来一局后 players[1].is_ai 保持 True。"""
    from app import ai_player
    fake = FakeChat('{"kind": "take_tokens", "cells": [0]}')
    monkeypatch.setattr(ai_player.ai_client, "chat", fake)

    r = client.post("/api/rooms", json={"nickname": "真人", "ai": True})
    data = r.json()
    with client.websocket_connect(
            f"/ws?room={data['room_code']}&token={data['token']}") as ws:
        recv_until(ws, "hello")
        st = recv_until(ws, "state")
        assert st["state"]["players"][1]["is_ai"] is True
        # 真人认输结束对局
        ws.send_json({"type": "action", "action": {"kind": "concede"}})
        st2 = recv_until(ws, "state")
        assert st2["state"]["winner"] == 1
        # 再来一局
        ws.send_json({"type": "rematch"})
        st3 = recv_until(ws, "state")
        assert st3["started"] is True
        assert st3["state"]["players"][1]["is_ai"] is True
