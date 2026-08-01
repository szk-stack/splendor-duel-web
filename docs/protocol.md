# WebSocket 消息协议

> 三处同步纪律：`server/app/protocol.py` ↔ 本文档 ↔ `web/src/types.ts`，改协议必须三处同改。

连接：`WS /ws?room={code}&token={token}`（认证失败 close code 4001）。
心跳：客户端每 25s 发 `ping`，服务端回 `pong`；服务端 60s 无帧即断开。

## 客户端 → 服务端

| type | 字段 | 说明 |
|---|---|---|
| `hello` | `nickname` | 连接后首帧（当前忽略，兼容用） |
| `action` | `action: {...}` | 行动提交，字段见引擎 Action |
| `rematch` | — | 对局结束后请求同房间再来一局 |
| `ping` | — | 心跳 |

## 服务端 → 客户端

| type | 字段 | 说明 |
|---|---|---|
| `hello` | `slot, opponent_nickname, started` | 连接确认 |
| `player_joined` | `slot, nickname` | 对手入座（大厅用，当前由 hello 携带） |
| `state` | `state, legal_actions?, events, started` | 全量状态广播；`legal_actions` 只给轮到的玩家；`events` 仅动画用 |
| `player_left` | `slot` | 对手掉线 |
| `opponent_reconnected` | `slot` | 对手重连 |
| `error` | `code, message, ref_action?` | 行动被拒 |
| `pong` | — | 心跳回执 |

## 错误码

`NOT_YOUR_TURN` / `GAME_OVER` / `INVALID_PHASE` / `ILLEGAL_ACTION` / `ROOM_NOT_FOUND` / `ROOM_FULL` / `AUTH_FAILED`（引擎其余错误码原样透传）。

## 引擎 Action（客户端提交）

| kind | 关键字段 | 说明 |
|---|---|---|
| `use_privilege` | `cell` | 可选行动：特权换 1 个非金币筹码 |
| `fill_board` | — | 可选行动：从布袋补充棋盘（对手获 1 特权） |
| `take_tokens` | `cells: [1..3]` | 相邻成线的非金币格 |
| `reserve` | `gold_cell, source(pyramid\|deck), tier, slot?` | 拿金币 + 保留牌 |
| `buy` | `source, tier, slot?/card_id?, payment, joker_target?, steal_color?, royal_steal_color?, take_cell?, royal_choice?` | 购买 + 能力选择 |
| `discard` | `colors: {color: n}` | 弃牌阶段，弃到 10 个 |
| `concede` | — | 认输（任意玩家随时可发，对手获胜，win_reason=concede） |

`payment` 格式：`{color: {tokens: n, gold: m}}`（color ∈ 五色+pearl）。
