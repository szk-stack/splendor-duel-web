"""AI 玩家：组装提示词 → 调用大模型 → 解析行动 → 引擎校验 → 重试/兜底。

AI 与真人共用同一引擎接口，模型输出非法行动会被引擎拒绝，
重试耗尽后从 legal_actions 随机选一个合法行动兜底，保证对局永不卡死。
"""
import json
import logging
import random

from engine.types import InvalidAction
from . import ai_client

log = logging.getLogger("splendor.ai")

MAX_RETRY = 2  # 非法行动后的重试次数（不含首次）

RULES_SUMMARY = """你是《璀璨宝石：对决》(Splendor Duel) 的 AI 玩家。规则要点：
- 目标：率先达成任一胜利条件——声望 20 分 / 收集 10 个皇冠 / 同色卡牌 10 分。
- 每回合先可执行 0~2 个可选行动（使用特权：放回1-3个特权换对应数量宝石/珍珠；补充棋盘：对手获1特权），然后必须执行 1 个强制行动。
- 强制行动三选一：①拿取最多3个相邻（横/竖/斜一条线）的宝石/珍珠，不能拿金币；②拿1金币+保留1张牌（唯一获得金币的方式，上限3张）；③购买一张珠宝牌（金币可充当任意宝石/珍珠，已购卡的奖励色可减免对应颜色费用）。
- 购买带皇冠的牌可累计皇冠；3/6 皇冠时可拿 1 张皇家牌（每人最多2张）；百搭(joker)奖励卡购买时须叠放到一张已有奖励的卡上并复制其颜色。
- 回合结束时手牌超过10个必须弃到10个。
- 博弈策略（必须严格执行，这是对局胜负的关键）：
  1. 你的目标是赢，不是"走一步"：每回合先分析——①对手在凑什么颜色/路线（看对手已购卡与手牌），②你可负担/可规划购买哪张卡，③棋盘上哪些筹码值得抢。
  2. 拿筹码是手段：优先一次性拿 2-3 个**同色**或**凑齐购买所需**的相邻筹码（成线），为下一张可负担的卡做准备；不要一次只拿 1 个，除非没有更好的选择。
  3. 有可负担的卡（buy 选项）时优先购买——奖励色与你已有卡同色的卡、高分卡、带皇冠的卡价值最高；购买后你的永久奖励会降低后续费用，形成滚雪球。
  4. 保留牌（reserve）是博弈工具，机会合适就要用：①对手已购某颜色卡、正需要该色更多卡时，保留该色的关键牌阻断对手；②棋盘上出现高分卡/高皇冠卡而你还买不起时，先保留锁定（会获得 1 金币）；③你只剩少量金币需求时，保留也是拿金币的途径。
  5. 干扰对手：如果对手明显在凑某个颜色拿同色 10 分，优先拿走/保留该颜色的关键卡，或抢占该颜色筹码。
  6. 胜利推进：中期以后（已购 3+ 张卡）优先购买**高分卡**（3 分以上）与能凑**同色 10 分**的卡，别只买 0-1 分小卡；接近胜利条件时集中所有资源冲刺。
  7. 三条胜利路线（20分/10皇冠/同色10分）选一条主攻，同时留意皇冠进度（3/6 皇冠可拿皇家牌）。
  8. 不要无脑囤筹码：手牌超过 10 会被迫弃牌，损失节奏；每回合都问问自己"这步离胜利更近了吗"。"""


_COLOR_LABEL = {"white": "白", "blue": "蓝", "green": "绿",
                "red": "红", "black": "黑", "pearl": "珠", "gold": "金"}


def render_board(board: list) -> str:
    """把 5x5 棋盘渲染成带索引的 ASCII 网格（模型更易理解行列关系）。"""
    lines = []
    for row in range(5):
        cells = []
        for col in range(5):
            i = row * 5 + col
            t = board[i]
            cells.append(f"{i:>2}:{_COLOR_LABEL.get(t, '·')}")
        lines.append("  ".join(cells))
    return "\n".join(lines)


def build_messages(state_dict: dict, legal_actions: dict, error: str = None) -> list:
    """组装提示词：规则 + ASCII 棋盘 + 当前局势 + 合法行动（+ 上次被拒原因）。"""
    hint = ""
    if legal_actions.get("discard"):
        hint = ("\n\n当前处于【弃牌阶段】：必须输出 {\"kind\": \"discard\", \"colors\": {\"颜色名\": 数量}}，"
                "各色数量合计必须恰好等于需弃数量，颜色名为 white/blue/green/red/black/pearl/gold。")
    user = (
        "棋盘（索引为 0-24，行主序：0-4 第一行、5-9 第二行…；"
        "拿筹码必须选同一行/列/斜线上连续相邻的格，金=金币不可拿；"
        "拿 3 个同色或 2 个珍珠会让对手获得特权，注意权衡）：\n"
        + render_board(state_dict["board"])
        + "\n\n当前局势（JSON，含双方手牌/已购卡/得分/皇冠）：\n"
        + json.dumps(state_dict, ensure_ascii=False)
        + "\n\n你可执行的合法行动（JSON）：\n"
        + json.dumps(legal_actions, ensure_ascii=False)
        + ("\n\n你上次提交的行动被拒绝：" + error if error else "")
        + hint
        + "\n\n先简要分析当前局势（对手威胁、你的购买目标、筹码取舍，两三句话即可），"
          "然后只输出行动 JSON 对象（如 {\"kind\": \"take_tokens\", \"cells\": [0, 1, 5]}）。"
          "分析文字随意，但最后必须包含 JSON。"
    )
    return [{"role": "system", "content": RULES_SUMMARY},
            {"role": "user", "content": user}]


def parse_action(text: str) -> dict:
    """从模型回复中提取 action JSON（容忍 markdown 代码块与多余文字）。"""
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        # 完整代码块取第 1 段；未闭合（只有开头）取剩余部分
        t = parts[1] if len(parts) >= 2 else ""
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("回复中无 JSON 对象")
    return json.loads(t[start:end + 1])


def random_legal_action(legal_actions: dict) -> dict:
    """兜底：从合法行动中构造一个可执行的随机行动（优先简单行动）。

    覆盖所有阶段：强制行动（拿/保留/补充/特权）、弃牌阶段、强制补充棋盘。
    """
    # 弃牌阶段：构造恰好弃 over 个的明细（跨颜色分摊）
    discard = legal_actions.get("discard")
    if discard:
        colors = {}
        over = discard["over"]
        for c, n in (discard.get("hand") or {}).items():
            if over <= 0:
                break
            take = min(over, n)
            if take:
                colors[c] = take
            over -= take
        if sum(colors.values()) == discard["over"]:
            return {"kind": "discard", "colors": colors}
        return None

    actions = legal_actions.get("actions") or []
    by_kind = {}
    for a in actions:
        by_kind.setdefault(a["kind"], []).append(a)
    # 强制补充棋盘（无任何强制行动可行时的唯一出路）
    if "force_fill" in by_kind:
        return {"kind": "fill_board"}
    for kind in ("take_tokens", "reserve", "use_privilege", "fill_board"):
        if kind not in by_kind:
            continue
        a = random.choice(by_kind[kind])
        if kind == "take_tokens":
            return {"kind": "take_tokens", "cells": [random.choice(a["cells"])]}
        if kind == "use_privilege":
            return {"kind": "use_privilege", "cells": [random.choice(a["cells"])]}
        if kind == "reserve":
            tiers = [t for t, slots in (a.get("pyramid") or {}).items() if slots]
            if tiers:
                tier = random.choice(tiers)
                return {"kind": "reserve", "source": "pyramid", "tier": int(tier),
                        "slot": random.choice(a["pyramid"][tier]),
                        "gold_cell": random.choice(a["gold_cells"])}
            if a.get("decks"):
                return {"kind": "reserve", "source": "deck",
                        "tier": random.choice(a["decks"]),
                        "gold_cell": random.choice(a["gold_cells"])}
            continue
        return {"kind": "fill_board"}
    return None


def _find_legal(legal_actions: dict, kind: str):
    for a in legal_actions.get("actions") or []:
        if a["kind"] == kind:
            return a
    return None


def _in_line(cells) -> bool:
    """与引擎一致的成线判定：排序后逐格相邻且方向一致。"""
    if len(cells) <= 1:
        return True
    s = sorted(cells)

    def d(a, b):
        return (a % 5 - b % 5, a // 5 - b // 5)

    dd = d(s[0], s[1])
    if dd == (0, 0) or max(abs(dd[0]), abs(dd[1])) > 1:
        return False
    for i in range(1, len(s) - 1):
        d2 = d(s[i], s[i + 1])
        if d2 != dd or max(abs(d2[0]), abs(d2[1])) > 1:
            return False
    return True


def best_take_cells(candidates, legal_cells) -> list:
    """从模型候选格中提取最大合法成线组合（3→2→1），全失败返回 None。

    保留模型的多格意图：成线就按多格拿，只有完全不合法才降级。
    """
    from itertools import combinations
    cand = [c for c in candidates if isinstance(c, int) and c in legal_cells]
    if not cand:
        return None
    for n in (3, 2, 1):
        for combo in combinations(sorted(set(cand)), n):
            if _in_line(combo):
                return list(combo)
    return None


def normalize_action(action: dict, game, legal_actions: dict) -> dict:
    """把模型的行动规范化为合法格式（AI 客户端内部修正，引擎仍权威校验）。

    - take_tokens/use_privilege：cells 过滤为合法格，取单格保证合法
    - buy：按模型意图匹配卡牌，自动生成支付明细与 joker/steal/royal 选择
    - reserve：补全 gold_cell 与牌位
    """
    if not isinstance(action, dict):
        return None
    kind = action.get("kind")

    if kind == "take_tokens":
        legal = _find_legal(legal_actions, "take_tokens")
        if not legal:
            return None
        combo = best_take_cells(action.get("cells") or [], legal["cells"])
        if not combo:
            return None
        return {"kind": "take_tokens", "cells": combo}

    if kind == "use_privilege":
        legal = _find_legal(legal_actions, "use_privilege")
        if not legal:
            return None
        legal_cells = set(legal["cells"])
        cells = [c for c in (action.get("cells") or [])
                 if isinstance(c, int) and c in legal_cells]
        if not cells:
            return None
        return {"kind": "use_privilege", "cells": cells[:1]}

    if kind == "reserve":
        legal = _find_legal(legal_actions, "reserve")
        if not legal or not legal.get("gold_cells"):
            return None
        gold = next((c for c in (action.get("gold_cell") and [action["gold_cell"]] or [])
                     if c in legal["gold_cells"]), legal["gold_cells"][0])
        # 优先模型想保留的明牌，其次牌库顶
        tier = action.get("tier")
        slot = action.get("slot")
        if isinstance(tier, int) and str(tier) in legal.get("pyramid", {}) \
                and slot in legal["pyramid"][str(tier)]:
            return {"kind": "reserve", "source": "pyramid",
                    "tier": tier, "slot": slot, "gold_cell": gold}
        if action.get("source") == "deck" and tier in legal.get("decks", []):
            return {"kind": "reserve", "source": "deck", "tier": tier, "gold_cell": gold}
        # 默认：随机一张明牌
        for t, slots in (legal.get("pyramid") or {}).items():
            if slots:
                return {"kind": "reserve", "source": "pyramid", "tier": int(t),
                        "slot": slots[0], "gold_cell": gold}
        if legal.get("decks"):
            return {"kind": "reserve", "source": "deck",
                    "tier": legal["decks"][0], "gold_cell": gold}
        return None

    if kind == "buy":
        legal = _find_legal(legal_actions, "buy")
        if not legal or not legal.get("options"):
            return None
        options = legal["options"]
        # 匹配模型意图的卡（by card_id 或 card.id），否则选第一个可负担的
        wanted = action.get("card_id")
        if not wanted:
            wanted = (action.get("card") or {}).get("id")
        opt = next((o for o in options if o["card"]["id"] == wanted), None) or options[0]

        p = game.state.player(1)
        eff = game.state._library.effective_cost(opt["card"], p.bonus())
        hand = p.tokens
        payment, gold_left = {}, hand["gold"]
        for color in ("white", "blue", "green", "red", "black", "pearl"):
            need = eff.get(color, 0)
            t = min(need, hand.get(color, 0))
            g = min(need - t, gold_left)
            gold_left -= g
            payment[color] = {"tokens": t, "gold": g}

        result = {"kind": "buy", "source": opt["source"], "payment": payment}
        if opt.get("tier") is not None:
            result["tier"] = opt["tier"]
        if opt.get("slot") is not None:
            result["slot"] = opt["slot"]
        if opt.get("card_id"):
            result["card_id"] = opt["card_id"]
        if opt.get("stack_targets"):
            result["joker_target"] = opt["stack_targets"][0]
        if opt.get("royal_required"):
            pool = game.state.royal_pool
            if pool:
                # 优先选非偷取能力的皇家牌（偷取需额外指定颜色，模型容易漏）
                royal = next(
                    (r for r in pool
                     if game.state._library.royal(r)["capacity"] != "steal_opponent_pawn"),
                    pool[0])
                result["royal_choice"] = royal
                if game.state._library.royal(royal)["capacity"] == "steal_opponent_pawn":
                    opp = game.state.opponent(1)
                    stealable = [c for c in ("white", "blue", "green", "red", "black", "pearl")
                                 if opp.tokens.get(c, 0) > 0]
                    if stealable:
                        result["royal_steal_color"] = stealable[0]
        if opt["card"]["capacity"] == "steal_opponent_pawn":
            opp = game.state.opponent(1)
            stealable = [c for c in ("white", "blue", "green", "red", "black", "pearl")
                         if opp.tokens.get(c, 0) > 0]
            if stealable:
                result["steal_color"] = stealable[0]
        if opt["card"]["capacity"] == "take_on_board" and opt["card"]["bonus"]:
            cell = next((i for i, t in enumerate(game.state.board)
                         if t == opt["card"]["bonus"]), None)
            if cell is not None:
                result["take_cell"] = cell
        return result

    # fill_board / force_fill / 其他：直接透传（引擎会校验）
    return action


async def ask_action(state_dict: dict, legal_actions: dict, error: str = None):
    """调用大模型获取行动。返回 (action, 错误信息)；解析/调用失败返回 (None, 原因)。"""
    try:
        messages = build_messages(state_dict, legal_actions, error)
        text = await ai_client.chat(messages, temperature=0.4, max_tokens=900)
        return parse_action(text), None
    except ai_client.AIError as e:
        return None, f"API 错误: {e}"
    except (ValueError, json.JSONDecodeError) as e:
        return None, f"解析失败: {e}"


async def take_turn(room, broadcast) -> bool:
    """AI 回合主循环：持续行动（含 replay/额外回合）直到轮到真人或对局结束。

    非法行动带错误信息回传模型重试（MAX_RETRY 次），耗尽后随机合法行动兜底。
    返回 True=正常完成；False=异常/无法推进（调用方决定是否重调度）。
    room.ai_busy 防止重复启动；真人断线时由调用方（main.py）决定不触发。
    """
    if room.ai_busy or room.game is None:
        return True
    room.ai_busy = True
    try:
        while True:
            game = room.game
            if game is None or game.state.phase == "game_over" \
                    or game.state.current != 1:
                return True
            if room.game is not game:
                # 对局已被替换（重开/退出），放弃过期任务
                log.warning("AI 任务检测到对局已替换，退出")
                return True
            try:
                legal = game.legal_actions(1)
                events = None
                error = None
                for attempt in range(MAX_RETRY + 1):
                    action, error = await ask_action(game.state_dict(1), legal, error)
                    if action is None:
                        log.warning("AI 第 %d 次尝试失败: %s", attempt + 1, error)
                        continue  # API/解析失败：带原因重试
                    action = normalize_action(action, game, legal)
                    if action is None:
                        error = "行动无法规范化（不在合法范围内）"
                        log.warning("AI 行动无法规范化: %s", error)
                        continue
                    try:
                        events = game.step(1, action)
                        log.info("AI 行动(第%d次尝试): %s",
                                 attempt + 1, json.dumps(action, ensure_ascii=False))
                        break
                    except InvalidAction as e:
                        error = f"{e.code}: {e.message}"
                        log.warning("AI 行动被拒: %s <- %s", error,
                                    json.dumps(action, ensure_ascii=False))
                if events is None:
                    # 重试耗尽：随机合法行动兜底
                    log.warning("AI 重试耗尽，随机兜底")
                    action = random_legal_action(legal)
                    if action is None:
                        log.error("AI 兜底失败：无合法行动可构造（阶段=%s）",
                                  game.state.phase)
                        return False
                    try:
                        events = game.step(1, action)
                    except InvalidAction:
                        return False
            except Exception:
                log.exception("AI 回合异常")
                return False
            await broadcast(events)
    finally:
        room.ai_busy = False
    return True
