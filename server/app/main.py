"""FastAPI 入口：REST + WebSocket。uvicorn 必须单 worker（房间在进程内存）。"""
import asyncio
import secrets
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from engine.data import get_library
from engine.game import Game
from engine.types import InvalidAction, Phase
from . import ai_player, config, protocol
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


async def _broadcast_state(room: Room, events: list, started: bool = False,
                           expect: object = None):
    """向双方广播个性化 state（保留牌按视角隐藏；legal_actions 只给轮到的玩家）。

    expect：调用方持有的 game 引用；对局已被替换时丢弃（防止旧事件混入新房状态）。
    """
    if room.game is None:
        return  # 对局已结束/替换（过期 AI 任务可能携带旧事件）
    if expect is not None and room.game is not expect:
        return  # 对局已被替换，旧任务的事件作废
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
    """开局：真人房双方连接后开局；人机房真人连接即开局。"""
    if room.game is not None or not room.is_full():
        return
    if room.ai_mode:
        # 人机模式：只需真人（slot 0）连接
        p0 = room.players.get(0)
        if p0 is None or p0.ws is None:
            return
    elif any(p.ws is None for p in room.players.values()):
        return  # 等对手也连上 WS 再开局
    room.seed = secrets.randbelow(2 ** 32)
    nicknames = {p.slot: p.nickname for p in room.players.values()}
    room.game = Game(get_library(), seed=room.seed,
                     nicknames=(nicknames[0], nicknames[1]))
    if room.ai_mode:
        room.game.state.players[1].is_ai = True
    room.status = "playing"
    room.touch()
    await _broadcast_state(room, [], started=True)
    _maybe_ai_turn(room)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket,
                      room: str = Query(...),
                      token: str = Query(...)):
    manager = app.state.manager
    r = manager.get(room)
    session = _session_for(r, token) if r else None
    # 拒绝：无会话、或 AI 会话（AI 永远不需要 WS 连接，防止凭据被劫持冒充）
    if session is None or session.is_ai:
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
        _maybe_ai_turn(r)  # 重连后若轮到 AI → 恢复 AI 回合

    # 消息循环（心跳：AI 房间放宽超时，普通房间 60s 无帧即断开）
    heartbeat = config.AI_WS_HEARTBEAT_TIMEOUT if r.ai_mode else config.WS_HEARTBEAT_TIMEOUT
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_json(),
                                          timeout=heartbeat)
            r.touch()
            mtype = data.get("type")
            if mtype == protocol.C_PING:
                await _send(websocket, {"type": protocol.S_PONG})
            elif mtype == protocol.C_ACTION:
                await _handle_action(r, session, data.get("action") or {})
            elif mtype == protocol.C_REMATCH:
                await _handle_rematch(r)
            elif mtype == protocol.C_LEAVE:
                await _handle_leave(r, session)
                break  # 退出后断开本连接
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
    _maybe_ai_turn(room)  # 真人行动后轮到 AI → 触发 AI 回合


async def _handle_leave(room: Room, session):
    """退出房间：释放席位。对局进行中则对手获胜（forfeit），房间回到等待状态。"""
    # 对局进行中 -> 对手获胜
    if room.game is not None and room.game.state.phase != Phase.GAME_OVER:
        game = room.game
        game.state.winner = 1 - session.slot
        game.state.win_reason = "forfeit"
        game.state.phase = Phase.GAME_OVER
        await _broadcast_state(room, [{"type": "game_over", "winner": 1 - session.slot,
                                       "reason": "forfeit"}])
    # 移除会话，释放席位（房间作为"桌子"保留，可用房间码重新加入）
    room.players.pop(session.slot, None)
    room.game = None
    room.status = "waiting"
    room.touch()
    # 最后一个玩家退出也不立即销毁房间：保留 30 分钟（清理任务回收），
    # 期间房间码仍可让朋友加入
    if not room.players:
        return
    opp = next(iter(room.players.values()))
    if opp.ws is not None:
        try:
            await _send(opp.ws, {"type": protocol.S_PLAYER_LEFT, "slot": session.slot})
        except Exception:
            pass


def _maybe_ai_turn(room: Room):
    """若轮到 AI 玩家且真人在线 → 启动 AI 回合任务（不阻塞事件循环）。"""
    if not room.ai_mode or room.game is None:
        return
    p0 = room.players.get(0)
    p1 = room.players.get(1)
    if p0 is None or p1 is None or not p1.is_ai:
        return
    if p0.ws is None:  # 真人不在线：暂停 AI
        return
    if room.game.state.phase == "game_over" or room.game.state.current != 1:
        return
    if not room.ai_busy:
        task = asyncio.create_task(
            ai_player.take_turn(room, lambda ev, g=room.game: _broadcast_state(room, ev, expect=g)))
        # 连续失败重调度上限：3 次后放弃并告警（对局无解需人工干预）
        room.ai_retry = getattr(room, "ai_retry", 0)

        def _on_done(t):
            if t.cancelled():
                return
            try:
                ok = t.result()
            except Exception:
                ok = False
            if not ok and room.game is not None \
                    and room.game.state.phase != "game_over" \
                    and room.game.state.current == 1:
                room.ai_retry += 1
                if room.ai_retry >= 3:
                    print(f"[AI] 连续 {room.ai_retry} 次失败，停止重调度（房间 {room.code} 需人工处理）",
                          flush=True)
                    return
                asyncio.get_running_loop().call_later(1, lambda: _maybe_ai_turn(room))
            else:
                room.ai_retry = 0

        task.add_done_callback(_on_done)
        asyncio.create_task(_ai_keepalive(room))  # AI 思考期间给真人发保活帧


async def _ai_keepalive(room: Room):
    """AI 回合期间每 25s 给真人发一帧，防止服务端心跳超时断开连接。

    每次循环实时取真人会话（真人可能掉线重连，ws 引用会更新）。
    """
    while room.ai_busy:
        await asyncio.sleep(25)
        p0 = room.players.get(0)
        if p0 and p0.ws is not None:
            try:
                await p0.ws.send_json({"type": protocol.S_AI_THINKING})
            except Exception:
                pass


async def _handle_rematch(room: Room):
    """对局结束后同房间重开一局（新种子，保留昵称）。"""
    if room.game is None or room.game.state.phase != "game_over":
        return
    room.seed = secrets.randbelow(2 ** 32)
    nicknames = {p.slot: p.nickname for p in room.players.values()}
    room.game = Game(get_library(), seed=room.seed,
                     nicknames=(nicknames[0], nicknames[1]))
    if room.ai_mode:
        room.game.state.players[1].is_ai = True
    room.status = "playing"
    room.touch()
    await _broadcast_state(room, [], started=True)
