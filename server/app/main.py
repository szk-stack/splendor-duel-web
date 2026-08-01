"""FastAPI 入口：REST + WebSocket。uvicorn 必须单 worker（房间在进程内存）。"""
import asyncio
import secrets
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.data import get_library
from engine.game import Game
from engine.types import InvalidAction
from . import config, protocol
from .api import router as api_router
from .rooms import Room, RoomError, RoomManager

app = FastAPI(title="璀璨宝石：对决", version="0.1.0")
app.state.manager = RoomManager()

# 开发环境 CORS（Vite dev server 跨端口访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
async def _startup():
    app.state.manager.start_cleanup()


# ---------------------------------------------------------------- WebSocket

def _send(ws: WebSocket, message: dict):
    return ws.send_json(message)


def _session_for(room: Room, token: str):
    for p in room.players.values():
        if p.token == token:
            return p
    return None


async def _broadcast_state(room: Room, events: list, started: bool = False):
    """向双方广播个性化 state（保留牌按视角隐藏；legal_actions 只给轮到的玩家）。"""
    for slot in (0, 1):
        p = room.players.get(slot)
        if p and p.ws is not None:
            legal = room.game.legal_actions(slot) if slot == room.game.state.current else None
            try:
                await p.ws.send_json({
                    "type": protocol.S_STATE,
                    "state": room.game.state_dict(slot),
                    "legal_actions": legal,
                    "events": events,
                    "started": started,
                })
            except Exception:
                pass


async def _start_game(room: Room):
    """双方都连接（WS 就位）后创建对局并广播开局状态。"""
    if room.game is not None or not room.is_full():
        return
    if any(p.ws is None for p in room.players.values()):
        return  # 等对手也连上 WS 再开局
    room.seed = secrets.randbelow(2 ** 32)
    nicknames = {p.slot: p.nickname for p in room.players.values()}
    room.game = Game(get_library(), seed=room.seed,
                     nicknames=(nicknames[0], nicknames[1]))
    room.status = "playing"
    room.touch()
    await _broadcast_state(room, [], started=True)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket,
                      room: str = Query(...),
                      token: str = Query(...)):
    manager = app.state.manager
    r = manager.get(room)
    session = _session_for(r, token) if r else None
    if session is None:
        await websocket.close(code=protocol.CLOSE_AUTH_FAILED, reason="认证失败")
        return

    await websocket.accept()
    # 顶替旧连接（同一玩家的新连接生效）
    if session.ws is not None:
        try:
            await session.ws.close(code=1000, reason="新连接")
        except Exception:
            pass
    session.ws = websocket
    session.disconnected_at = None
    r.touch()

    # 欢迎帧
    opponent = next((p for p in r.players.values() if p.slot != session.slot), None)
    await _send(websocket, {
        "type": protocol.S_HELLO,
        "slot": session.slot,
        "opponent_nickname": opponent.nickname if opponent else None,
        "started": r.game is not None,
    })

    if r.game is None:
        await _start_game(r)  # 双方就位即开局
    else:
        # 重连：通知对手，补发全量状态
        opp = r.players.get(1 - session.slot)
        if opp and opp.ws is not None:
            await _send(opp.ws, {"type": protocol.S_OPPONENT_RECONNECTED,
                                 "slot": session.slot})
        await _send(websocket, {
            "type": protocol.S_STATE,
            "state": r.game.state_dict(session.slot),
            "legal_actions": r.game.legal_actions(session.slot)
            if session.slot == r.game.state.current else None,
            "events": [],
            "started": False,
        })

    # 消息循环（心跳：服务端 60s 无帧即断开）
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_json(),
                                          timeout=config.WS_HEARTBEAT_TIMEOUT)
            r.touch()
            mtype = data.get("type")
            if mtype == protocol.C_PING:
                await _send(websocket, {"type": protocol.S_PONG})
            elif mtype == protocol.C_ACTION:
                await _handle_action(r, session, data.get("action") or {})
            elif mtype == protocol.C_REMATCH:
                await _handle_rematch(r)
            # hello 首帧仅作兼容，忽略
    except asyncio.TimeoutError:
        await websocket.close(code=1000, reason="心跳超时")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        session.ws = None
        session.disconnected_at = time.time()
        if r.game is not None:
            opp = r.players.get(1 - session.slot)
            if opp and opp.ws is not None:
                try:
                    await _send(opp.ws, {"type": protocol.S_PLAYER_LEFT,
                                         "slot": session.slot})
                except Exception:
                    pass


async def _handle_action(room: Room, session, action: dict):
    if room.game is None or room.game.state.winner is not None:
        await _send(session.ws, {"type": protocol.S_ERROR,
                                 "code": protocol.ERR_GAME_OVER,
                                 "message": "对局已结束"})
        return
    try:
        events = room.game.step(session.slot, action)
    except InvalidAction as e:
        await _send(session.ws, {"type": protocol.S_ERROR, "code": e.code,
                                 "message": e.message, "ref_action": action})
        return
    await _broadcast_state(room, events)


async def _handle_rematch(room: Room):
    """对局结束后同房间重开一局（新种子，保留昵称）。"""
    if room.game is None or room.game.state.phase != "game_over":
        return
    room.seed = secrets.randbelow(2 ** 32)
    nicknames = {p.slot: p.nickname for p in room.players.values()}
    room.game = Game(get_library(), seed=room.seed,
                     nicknames=(nicknames[0], nicknames[1]))
    room.status = "playing"
    room.touch()
    await _broadcast_state(room, [], started=True)
