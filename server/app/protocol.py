"""WebSocket 消息协议常量。

三处同步纪律：本文件 <-> docs/protocol.md <-> web/src/types.ts，改协议必须三处同改。
"""

# 客户端 -> 服务端
C_HELLO = "hello"            # {nickname}（连接后首帧）
C_ACTION = "action"          # {action: {...}}
C_REMATCH = "rematch"        # 对局结束后请求再来一局（同房间重开）
C_LEAVE = "leave"            # 退出房间（释放席位；对局中则对手获胜）
C_PING = "ping"              # 心跳

# 服务端 -> 客户端
S_HELLO = "hello"            # {slot, opponent_nickname?, started}
S_PLAYER_JOINED = "player_joined"   # {slot, nickname}
S_STATE = "state"            # {state, legal_actions?, events, started}
S_PLAYER_LEFT = "player_left"       # {slot}（对手掉线）
S_OPPONENT_RECONNECTED = "opponent_reconnected"  # {slot}
S_ERROR = "error"            # {code, message, ref_action?}
S_PONG = "pong"
S_AI_THINKING = "ai_thinking"  # AI 思考中（保活帧，前端可忽略）

# 连接认证失败 / 房间关闭的 WebSocket close code
CLOSE_AUTH_FAILED = 4001
CLOSE_ROOM_CLOSED = 1001

# 错误码（客户端可据此提示）
ERR_NOT_YOUR_TURN = "NOT_YOUR_TURN"
ERR_GAME_OVER = "GAME_OVER"
ERR_INVALID_PHASE = "INVALID_PHASE"
ERR_ILLEGAL_ACTION = "ILLEGAL_ACTION"
ERR_ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
ERR_ROOM_FULL = "ROOM_FULL"
ERR_AUTH_FAILED = "AUTH_FAILED"
