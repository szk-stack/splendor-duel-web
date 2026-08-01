"""房间管理：创建/加入/生命周期。房间状态在进程内存，uvicorn 必须单 worker。"""
import asyncio
import secrets
import time
from dataclasses import dataclass, field

from . import config

# 房间码字符集（去掉易混淆的 0/1/I/O）
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5

NICK_MAX = 16


class RoomError(Exception):
    def __init__(self, code: str, message: str, http: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


@dataclass
class PlayerSession:
    slot: int
    token: str
    nickname: str
    ws: object = None          # WebSocket | None
    disconnected_at: float = None
    is_ai: bool = False        # AI 玩家（人机模式）无真实连接


@dataclass
class Room:
    code: str
    creator_nickname: str = ""
    players: dict = field(default_factory=dict)   # slot -> PlayerSession
    game: object = None                            # Game | None
    status: str = "waiting"                        # waiting|playing|finished
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    seed: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ai_mode: bool = False                          # 人机模式：slot 1 为 AI
    ai_busy: bool = False                          # AI 回合任务进行中

    def touch(self):
        self.last_activity = time.time()

    def is_full(self) -> bool:
        return len(self.players) >= 2


def sanitize_nickname(nickname: str) -> str:
    n = (nickname or "").strip()
    if not n:
        raise RoomError("BAD_NICKNAME", "昵称不能为空")
    if len(n) > NICK_MAX:
        n = n[:NICK_MAX]
    return n


class RoomManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self._cleanup_task = None

    def start_cleanup(self):
        """启动后台清理任务（app 启动时调用一次）。"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(config.CLEANUP_INTERVAL)
            now = time.time()
            dead = []
            for code, room in self.rooms.items():
                if now - room.last_activity > config.ROOM_TTL:
                    dead.append(code)
                elif not room.players:
                    # 空房间（全员退出）保留 ABANDON_TTL 供房间码重进
                    if now - room.last_activity > config.ABANDON_TTL:
                        dead.append(code)
                elif all(p.disconnected_at for p in room.players.values()) \
                        and now - min(p.disconnected_at for p in room.players.values()) \
                        > config.ABANDON_TTL:
                    dead.append(code)
            for code in dead:
                await self.close_room(code, "房间已关闭")

    async def close_room(self, code: str, reason: str):
        room = self.rooms.pop(code, None)
        if room is None:
            return
        for p in room.players.values():
            if p.ws is not None:
                try:
                    await p.ws.close(code=1001, reason=reason)
                except Exception:
                    pass

    def create(self, nickname: str, ai: bool = False) -> tuple:
        """创建房间，返回 (code, token, slot=0)。ai=True 时 slot 1 为 AI 玩家。"""
        nickname = sanitize_nickname(nickname)
        code = self._gen_code()
        room = Room(code=code, creator_nickname=nickname, ai_mode=ai)
        token = secrets.token_urlsafe(24)
        room.players[0] = PlayerSession(slot=0, token=token, nickname=nickname)
        if ai:
            room.players[1] = PlayerSession(slot=1, token="AI", nickname="AI", is_ai=True)
            room.status = "waiting"  # 真人连接后即开局
        self.rooms[code] = room
        return code, token, 0

    def join(self, code: str, nickname: str) -> tuple:
        """加入房间，返回 (code, token, slot)。优先分配空闲席位（退出后 slot 0 可能空闲）。"""
        code = code.strip().upper()
        room = self.rooms.get(code)
        if room is None:
            raise RoomError("ROOM_NOT_FOUND", "房间不存在", 404)
        if room.status != "waiting" or room.is_full():
            raise RoomError("ROOM_FULL", "房间已满或对局已开始", 409)
        nickname = sanitize_nickname(nickname)
        token = secrets.token_urlsafe(24)
        slot = 0 if 0 not in room.players else 1
        room.players[slot] = PlayerSession(slot=slot, token=token, nickname=nickname)
        room.game = None  # 新玩家入座后重开新局
        room.touch()
        return code, token, slot

    def get(self, code: str) -> Room:
        return self.rooms.get(code.strip().upper())

    def _gen_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                return code
