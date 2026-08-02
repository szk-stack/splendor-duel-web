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
    # 双方收到开局状态（先后手随机）
    state0 = recv_until(ws0, "state")
    state1 = recv_until(ws1, "state")
    assert state0["started"] and state1["started"]
    assert state0["state"]["phase"] == "optional"
    assert len(state0["state"]["board"]) == 25
    starter = state0["state"]["current"]
    first_ws, second_ws = (ws0, ws1) if starter == 0 else (ws1, ws0)
    assert (state0["legal_actions"] is not None) == (starter == 0)  # 先手有合法行动
    assert (state1["legal_actions"] is not None) == (starter == 1)

    # 先手非法行动 -> 收到 error
    first_ws.send_json({"type": "action", "action": {"kind": "take_tokens", "cells": []}})
    err = recv_until(first_ws, "error")
    assert err["code"] in ("ILLEGAL_ACTION",)

    # 先手拿 1 个筹码 -> 双方收到状态更新
    cell = next(i for i, t in enumerate(state0["state"]["board"]) if t != "gold")
    first_ws.send_json({"type": "action", "action": {"kind": "take_tokens", "cells": [cell]}})
    ns0 = recv_until(ws0, "state")
    ns1 = recv_until(ws1, "state")
    assert ns0["state"]["current"] == 1 - starter
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
    assert st["state"]["current"] == 1 - starter

    ctx0b.__exit__(None, None, None)
    ctx1.__exit__(None, None, None)


def test_concede_and_rematch(client):
    """认输结束对局 -> 再来一局重开。"""
    r0 = create_room(client, "A")
    r1 = join_room(client, r0["room_code"], "B")
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ctx1, ws1 = _open_ws(client, r0["room_code"], r1["token"])
    recv_until(ws1, "hello")
    recv_until(ws0, "state")
    recv_until(ws1, "state")

    # 认输
    ws0.send_json({"type": "action", "action": {"kind": "concede"}})
    st0 = recv_until(ws0, "state")
    st1 = recv_until(ws1, "state")
    assert st0["state"]["winner"] == 1
    assert st0["state"]["win_reason"] == "concede"
    assert st0["events"][-1]["type"] == "game_over"

    # 再来一局
    ws1.send_json({"type": "rematch"})
    rs0 = recv_until(ws0, "state")
    rs1 = recv_until(ws1, "state")
    assert rs0["started"] and rs1["started"]
    assert rs0["state"]["winner"] is None
    assert rs0["state"]["turn"] == 0
    assert rs0["state"]["phase"] == "optional"
    # 昵称保留
    assert rs0["state"]["players"][0]["nickname"] == "A"

    ctx0.__exit__(None, None, None)
    ctx1.__exit__(None, None, None)


def test_leave_midgame_rejoin(client):
    """对局中退出：对手获胜(forfeit)；席位释放后可重新加入并开新局。"""
    r0 = create_room(client, "A")
    r1 = join_room(client, r0["room_code"], "B")
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ctx1, ws1 = _open_ws(client, r0["room_code"], r1["token"])
    recv_until(ws1, "hello")
    recv_until(ws0, "state")
    recv_until(ws1, "state")

    # 0 号退出 -> 1 号获胜（forfeit）
    ws0.send_json({"type": "leave"})
    st = recv_until(ws1, "state")
    assert st["state"]["winner"] == 1
    assert st["state"]["win_reason"] == "forfeit"
    # 0 号连接被服务端断开
    ctx0.__exit__(None, None, None)

    # 新玩家（或原玩家）可用房间码重新加入
    r2 = client.post(f"/api/rooms/{r0['room_code']}/join", json={"nickname": "C"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["slot"] == 0  # 空闲席位
    ctx2, ws2 = _open_ws(client, r0["room_code"], r2.json()["token"])
    recv_until(ws2, "hello")
    # 双方连接后开新局
    st1 = recv_until(ws1, "state")
    st2 = recv_until(ws2, "state")
    assert st1["started"] and st2["started"]
    assert st1["state"]["winner"] is None

    ctx2.__exit__(None, None, None)
    ctx1.__exit__(None, None, None)


def test_last_player_leave_room_survives(client):
    """最后一个玩家退出后房间保留（30 分钟窗口），房间码仍可加入。"""
    r0 = create_room(client, "A")
    r1 = join_room(client, r0["room_code"], "B")
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ctx1, ws1 = _open_ws(client, r0["room_code"], r1["token"])
    recv_until(ws1, "hello")
    recv_until(ws0, "state")
    recv_until(ws1, "state")

    # A 退出（对局中 -> B 获胜 forfeit），房间剩 B
    ws0.send_json({"type": "leave"})
    recv_until(ws1, "state")
    ctx0.__exit__(None, None, None)

    # B 也退出 -> 房间空，但不销毁
    ws1.send_json({"type": "leave"})
    ctx1.__exit__(None, None, None)

    # 房间码仍可加入（slot 0）
    r2 = client.post(f"/api/rooms/{r0['room_code']}/join", json={"nickname": "C"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["slot"] == 0
    ctx2, ws2 = _open_ws(client, r0["room_code"], r2.json()["token"])
    hello = recv_until(ws2, "hello")
    assert hello["started"] is False  # 等待中，未开局
    ctx2.__exit__(None, None, None)


def test_join_by_nickname_reclaims_disconnected_slot(client):
    """断线玩家按用户名凭证重新加入：对局进行中可恢复，不同昵称被拒。"""
    r0 = create_room(client, "Alice")
    r1 = join_room(client, r0["room_code"], "Bob")
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ctx1, ws1 = _open_ws(client, r0["room_code"], r1["token"])
    recv_until(ws1, "hello")
    st0 = recv_until(ws0, "state")
    recv_until(ws1, "state")

    # 房主（Alice）断线（关页面，未走 leave）
    ctx0.__exit__(None, None, None)
    recv_until(ws1, "player_left")

    # 不同昵称加入 → 409
    resp = client.post(f"/api/rooms/{r0['room_code']}/join", json={"nickname": "路人"})
    assert resp.status_code == 409

    # 同昵称加入 → 接管席位成功
    resp = client.post(f"/api/rooms/{r0['room_code']}/join", json={"nickname": "Alice"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slot"] == 0
    assert data["token"] != r0["token"]  # 新 token

    # 接管后连接 → 恢复对局（重连分支，发全量状态）
    ctx2, ws2 = _open_ws(client, r0["room_code"], data["token"])
    hello = recv_until(ws2, "hello")
    assert hello["started"] is True
    st = recv_until(ws2, "state")
    # 断线前无人行动过，对局状态原样延续
    assert st["state"]["current"] == st0["state"]["current"]

    ctx2.__exit__(None, None, None)
    ctx1.__exit__(None, None, None)


def test_ping_pong(client):
    r0 = create_room(client)
    ctx0, ws0 = _open_ws(client, r0["room_code"], r0["token"])
    recv_until(ws0, "hello")
    ws0.send_json({"type": "ping"})
    pong = recv_until(ws0, "pong")
    assert pong["type"] == "pong"
    ctx0.__exit__(None, None, None)
