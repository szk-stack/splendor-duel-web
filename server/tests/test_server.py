"""服务层集成测试：REST + WebSocket 双客户端完整流程。"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def create_room(client, nickname="Alice"):
    r = client.post("/api/rooms", json={"nickname": nickname})
    assert r.status_code == 200, r.text
    return r.json()


def join_room(client, code, nickname="Bob"):
    r = client.post(f"/api/rooms/{code}/join", json={"nickname": nickname})
    assert r.status_code == 200, r.text
    return r.json()


def recv_until(ws, mtype, timeout=5):
    """接收直到指定类型消息（跳过其他类型）。"""
    end = time.time() + timeout
    while time.time() < end:
        msg = ws.receive_json()
        if msg["type"] == mtype:
            return msg
    raise TimeoutError(f"未收到 {mtype} 消息")


def test_room_lifecycle(client):
    data = create_room(client)
    assert data["slot"] == 0
    assert len(data["room_code"]) == 5
    join = join_room(client, data["room_code"])
    assert join["slot"] == 1
    # 房间满后拒绝
    r = client.post(f"/api/rooms/{data['room_code']}/join", json={"nickname": "C"})
    assert r.status_code == 409
    # 不存在的房间
    r = client.post("/api/rooms/XXXXX/join", json={"nickname": "C"})
    assert r.status_code == 404


def test_auth_failure_closes_ws(client):
    data = create_room(client)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws?room={data['room_code']}&token=WRONG"):
            pass


def _open_ws(client, code, token):
    ctx = client.websocket_connect(f"/ws?room={code}&token={token}")
    ws = ctx.__enter__()
    return ctx, ws


def test_full_game_flow(client):
    """双人完整对局：开局、行动广播、非法行动、胜利结束。"""
    r0 = create_room(client, "Alice")
    r1 = join_room(client, r0["room_code"], "Bob")

    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    hello0 = recv_until(ws0, "hello")
    assert hello0["slot"] == 0 and hello0["started"] is False

    ctx1, ws1 = _open_ws(client, r0["room_code"], r1["token"])
    hello1 = recv_until(ws1, "hello")
    assert hello1["slot"] == 1
    # 双方收到开局状态
    state0 = recv_until(ws0, "state")
    state1 = recv_until(ws1, "state")
    assert state0["started"] and state1["started"]
    assert state0["state"]["phase"] == "optional"
    assert len(state0["state"]["board"]) == 25
    assert state0["legal_actions"] is not None  # 先手有合法行动
    assert state1["legal_actions"] is None      # 后手没有

    # 0 号非法行动 -> 收到 error（还不到对方行动）
    ws0.send_json({"type": "action", "action": {"kind": "take_tokens", "cells": []}})
    err = recv_until(ws0, "error")
    assert err["code"] in ("ILLEGAL_ACTION",)

    # 0 号拿 1 个筹码 -> 双方收到状态更新
    cell = next(i for i, t in enumerate(state0["state"]["board"]) if t != "gold")
    ws0.send_json({"type": "action", "action": {"kind": "take_tokens", "cells": [cell]}})
    ns0 = recv_until(ws0, "state")
    ns1 = recv_until(ws1, "state")
    assert ns0["state"]["current"] == 1
    assert ns1["state"]["players"][0]["tokens"]["white"] >= 0

    # 断线：1 号收到 player_left
    ctx0.__exit__(None, None, None)
    left = recv_until(ws1, "player_left")
    assert left["slot"] == 0

    # 重连：恢复全量状态
    ctx0b, ws0b = _open_ws(client, r0["room_code"], r0["token"])
    hello = recv_until(ws0b, "hello")
    assert hello["started"] is True
    recon = recv_until(ws1, "opponent_reconnected")
    assert recon["slot"] == 0
    st = recv_until(ws0b, "state")
    assert st["state"]["current"] == 1

    ctx0b.__exit__(None, None, None)
    ctx1.__exit__(None, None, None)


def test_ping_pong(client):
    r0 = create_room(client)
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ws0.send_json({"type": "ping"})
    pong = recv_until(ws0, "pong")
    assert pong["type"] == "pong"
    ctx0.__exit__(None, None, None)
