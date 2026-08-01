"""运行配置（环境变量可覆盖）。"""
import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


# 断线重连窗口（秒）：超时未重连视为放弃
DISCONNECT_GRACE = _int("SPLENDOR_DISCONNECT_GRACE", 120)
# 房间闲置 TTL（秒）
ROOM_TTL = _int("SPLENDOR_ROOM_TTL", 2 * 3600)
# 双方断线废弃 TTL（秒）
ABANDON_TTL = _int("SPLENDOR_ABANDON_TTL", 30 * 60)
# WebSocket 心跳超时（秒）：客户端每 25s ping，服务端 60s 无帧即断开
WS_HEARTBEAT_TIMEOUT = _int("SPLENDOR_WS_HEARTBEAT", 60)
# AI 房间心跳超时（秒）：AI 思考可能超过 60s，放宽防止真人被误断
AI_WS_HEARTBEAT_TIMEOUT = _int("SPLENDOR_AI_WS_HEARTBEAT", 180)
# 清理任务周期（秒）
CLEANUP_INTERVAL = _int("SPLENDOR_CLEANUP_INTERVAL", 60)
