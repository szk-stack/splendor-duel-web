"""AI 对局日志：记录每步双方操作与 AI 思考原文，便于复盘与模型学习。

日志文件保存在项目根目录 logs/ 下，格式为可读 Markdown：
  logs/game_YYYYMMDD_HHMMSS_<房间码>.md
每局一个文件；AI 的完整模型回复（含分析文字）会被记录，作为学习/调优素材。
"""
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"

_COLOR_CN = {"white": "白", "blue": "蓝", "green": "绿", "red": "红",
             "black": "黑", "pearl": "珍珠", "gold": "金币"}


def _payment_desc(payment) -> str:
    parts = []
    for c, v in (payment or {}).items():
        t, g = v.get("tokens", 0), v.get("gold", 0)
        if t or g:
            parts.append(f"{_COLOR_CN.get(c, c)}×{t}" + (f"+金{g}" if g else ""))
    return "、".join(parts) or "免费"


def action_desc(action: dict) -> str:
    """行动 JSON → 中文描述（可读）。"""
    kind = action.get("kind")
    if kind == "take_tokens":
        cells = action.get("cells", [])
        return f"拿筹码 {cells}"
    if kind == "use_privilege":
        return f"使用特权换 {len(action.get('cells') or [])} 个筹码"
    if kind == "fill_board":
        return "补充棋盘"
    if kind == "reserve":
        src = action.get("source")
        if src == "pyramid":
            return f"保留 {action.get('tier')}级第{action.get('slot')}位的明牌，拿 1 金币"
        return f"从 {action.get('tier')}级牌库顶盲保留一张，拿 1 金币"
    if kind == "buy":
        desc = f"购买 {action.get('card_id')}（支付 {_payment_desc(action.get('payment'))}"
        extra = []
        if action.get("joker_target"):
            extra.append(f"叠放到{action['joker_target']}")
        if action.get("royal_choice"):
            extra.append(f"获皇家牌{action['royal_choice']}")
        if action.get("steal_color"):
            extra.append(f"偷取{_COLOR_CN.get(action['steal_color'], action['steal_color'])}")
        if action.get("royal_steal_color"):
            extra.append(f"皇家牌偷取{_COLOR_CN.get(action['royal_steal_color'], action['royal_steal_color'])}")
        return desc + ("；" + "；".join(extra) if extra else "") + ")"
    if kind == "discard":
        return "弃牌 " + "、".join(f"{_COLOR_CN.get(c, c)}×{n}" for c, n in (action.get("colors") or {}).items())
    if kind == "concede":
        return "认输"
    return str(action)


def _player_line(p) -> str:
    hand = " ".join(f"{_COLOR_CN[c]}×{n}" for c, n in p["tokens"].items() if n) or "无"
    return (f"手牌[{hand}] | 得分{p['points']} 已购{len(p['bought'])} 皇冠{p['crowns']} "
            f"特权{p['privileges']} 保留{len(p['reserved'])}")


# ---------------------------------------------------------------- 实时日志条目

_CAPACITY_EFFECT_CN = {
    "replay": "获得额外回合",
    "take_priviledge": "获得1个特权",
}


def _card_public(card: dict) -> dict:
    """卡牌对外数据（与引擎 state 序列化同款，前端可复用 CardView 渲染）。"""
    return {
        "id": card["id"], "level": card["level"], "points": card["points"],
        "bonus": card["bonus"], "bonus_number": card["bonus_number"],
        "crowns": card["crowns"], "capacity": card["capacity"],
        "cost": dict(card["cost"]),
    }


def _royal_public(royal: dict) -> dict:
    return {"id": royal["id"], "points": royal["points"], "capacity": royal["capacity"]}


def _capacity_effects(capacity, action: dict, opponent_hand: dict, board_before: list,
                      bonus_color=None) -> list:
    """卡牌/皇家牌能力 → 中文效果描述（含未生效分支）。"""
    if not capacity:
        return []
    if capacity == "replay":
        return ["获得额外回合"]
    if capacity == "take_priviledge":
        return ["获得1个特权"]
    if capacity == "steal_opponent_pawn":
        color = action.get("steal_color") or action.get("royal_steal_color")
        if color and opponent_hand.get(color, 0) > 0:
            return [f"偷取了对方的1个{_COLOR_CN.get(color, color)}"]
        return ["偷取（对方没有可偷筹码，效果未生效）"]
    if capacity == "take_on_board":
        color = bonus_color
        if color and color in (board_before or []):
            return [f"从棋盘拿取1个{_COLOR_CN.get(color, color)}指示物"]
        return [f"拿取{_COLOR_CN.get(color, color) if color else ''}指示物（棋盘无该色，效果未生效）"]
    return []


def build_log_entry(action: dict, board_before: list, state, library, slot: int,
                    nickname: str) -> dict:
    """行动 → 结构化日志条目（实时日志面板用，含完整卡面与能力效果）。"""
    kind = action.get("kind")
    p = state.players[slot]
    opponent = state.players[1 - slot]
    entry = {
        "player": nickname,
        "type": kind,
        "turn": state.turn,
    }

    if kind == "take_tokens":
        cells = action.get("cells") or []
        colors = {}
        for c in cells:
            if 0 <= c < len(board_before) and board_before[c]:
                color = board_before[c]
                colors[color] = colors.get(color, 0) + 1
        entry["tokens"] = colors

    elif kind == "use_privilege":
        cells = action.get("cells") or []
        colors = {}
        for c in cells:
            if 0 <= c < len(board_before) and board_before[c]:
                color = board_before[c]
                colors[color] = colors.get(color, 0) + 1
        entry["privileges_used"] = len(cells)
        entry["tokens"] = colors

    elif kind == "fill_board":
        pass  # 无附加数据

    elif kind == "reserve":
        cid = None
        if action.get("source") == "pyramid":
            tier = action.get("tier")
            slot_idx = action.get("slot")
            # 保留后展示区已补牌，无法从 state 反查原卡——用保留区新增的卡
            reserved = p.reserved
            if reserved:
                cid = reserved[-1]
        else:
            reserved = p.reserved
            if reserved:
                cid = reserved[-1]
        if cid and cid in library.cards:
            entry["card"] = _card_public(library.card(cid))

    elif kind == "buy":
        cid = action.get("card_id")
        if not cid:
            # 金字塔购买：action 无 card_id（只有 tier/slot）——从已购最后一张推
            if p.bought:
                cid = p.bought[-1]["id"]
        if cid and cid in library.cards:
            card = library.card(cid)
            entry["card"] = _card_public(card)
            entry["payment"] = dict(action.get("payment") or {})
            # 卡牌能力效果
            entry["effects"] = _capacity_effects(
                card["capacity"], action, opponent.tokens, board_before,
                bonus_color=card["bonus"])
        # 皇家卡（buy 触发）
        rc = action.get("royal_choice")
        if rc and rc in library.royal_cards:
            royal = library.royal(rc)
            entry["royal_card"] = _royal_public(royal)
            entry["royal_index"] = len(p.royal_cards) + 1  # 第几张（获得后）
            royal_effects = _capacity_effects(
                royal["capacity"], action, opponent.tokens, board_before)
            entry["effects"] = (entry.get("effects") or []) + royal_effects

    elif kind == "discard":
        entry["tokens"] = dict(action.get("colors") or {})

    elif kind == "concede":
        pass

    return entry


class GameLogger:
    """单局对局日志。"""

    def __init__(self, room_code: str, nickname0: str = "真人", nickname1: str = "AI"):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.path = LOG_DIR / f"game_{ts}_{room_code}.md"
        self._f = open(self.path, "w", encoding="utf-8")
        self._f.write(f"# 对局日志 · 房间 {room_code}\n")
        self._f.write(f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._f.write(f"- 玩家：{nickname0}（真人） vs {nickname1}（AI）\n\n")
        self._f.flush()

    def log_action(self, slot: int, nickname: str, action: dict, state,
                   ai_raw: str = None, is_ai: bool = False) -> None:
        """记录一步行动。state 为行动后的对局状态；ai_raw 为 AI 模型回复原文。"""
        p = state["players"][slot]
        line = [f"**{nickname}**：{action_desc(action)}"]
        if ai_raw:
            # AI 思考原文（模型学习素材）
            line.append(f"  > AI 思考：{ai_raw.strip().replace(chr(10), ' ')[:400]}")
        line.append(f"  > {_player_line(p)}")
        self._f.write("\n".join(line) + "\n\n")
        self._f.flush()

    def log_result(self, winner: int, reason: str, state) -> None:
        names = {0: state["players"][0]["nickname"], 1: state["players"][1]["nickname"]}
        self._f.write(f"## 对局结束\n")
        if winner is None:
            self._f.write(f"无胜者（对局中断）\n")
        else:
            self._f.write(f"**{names.get(winner, winner)} 获胜**（原因：{reason}）\n")
        self._f.write(f"- {_player_line(state['players'][0])}\n")
        self._f.write(f"- {_player_line(state['players'][1])}\n")
        self._f.flush()

    def close(self) -> None:
        try:
            self._f.close()
        except Exception:
            pass
