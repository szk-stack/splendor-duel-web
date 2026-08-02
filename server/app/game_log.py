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
