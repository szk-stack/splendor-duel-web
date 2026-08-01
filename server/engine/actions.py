"""行动校验与执行：validate/apply 纯函数。validate 不修改状态，apply 就地修改。"""
from .types import InvalidAction, Phase, GEM_COLORS, TOKEN_COLORS
from .win import check_win

# 支付涉及的筹码颜色（5 色 + 珍珠；金币为百搭，另行核算）
PAY_COLORS = GEM_COLORS + ["pearl"]


def _err(code: str, msg: str):
    raise InvalidAction(code, msg)


# ---------------------------------------------------------------- 工具函数

def _cell_rc(cell: int) -> tuple:
    return cell // 5, cell % 5


def _direction(a: int, b: int):
    """两格方向 (dr, dc)，非相邻返回 None。"""
    ra, ca = _cell_rc(a)
    rb, cb = _cell_rc(b)
    dr, dc = ra - rb, ca - cb
    if (dr, dc) in ((0, 0),) or abs(dr) > 1 or abs(dc) > 1:
        return None
    return dr, dc


def _tokens_on_board(state) -> list:
    return [i for i, t in enumerate(state.board) if t is not None]


def _non_gold_cells(state) -> list:
    return [i for i, t in enumerate(state.board) if t is not None and t != "gold"]


def _gold_cells(state) -> list:
    return [i for i, t in enumerate(state.board) if t == "gold"]


def _gain_privilege(state, slot: int) -> list:
    """给 slot 玩家 1 个特权；已满 3 个无事发生；无池时从对手拿取。"""
    p = state.player(slot)
    events = []
    if p.privileges >= state._rules["max_privileges"]:
        return events
    pool = state.privilege_pool
    if pool > 0:
        state.privilege_pool -= 1
        p.privileges += 1
        events.append({"type": "privilege_gained", "player": slot})
    else:
        other = state.opponent(slot)
        if other.privileges > 0:
            other.privileges -= 1
            p.privileges += 1
            events.append({"type": "privilege_gained", "player": slot})
    return events


def _add_token_to_hand(state, slot: int, color: str) -> None:
    state.player(slot).tokens[color] += 1


def _refill_pyramid(state, tier: int, slot: int) -> None:
    """从对应牌库补一张到指定槽位（若牌库非空）。"""
    deck = state.decks[tier]
    if deck and state.pyramid[tier][slot] is None:
        state.pyramid[tier][slot] = deck.pop()


def _fill_board_from_bag(state, rng) -> list:
    """按螺旋顺序从布袋补满空位；返回补入的格子列表。"""
    filled = []
    for cell in state._rules["spiral_order"]:
        if state.board[cell] is None:
            total = sum(state.bag.values())
            if total == 0:
                break
            color = rng.choices(list(state.bag), weights=list(state.bag.values()))[0]
            state.bag[color] -= 1
            state.board[cell] = color
            filled.append(cell)
    return filled


def _affordable(state, card) -> bool:
    """费用可负担（金币可拆分覆盖任意颜色）。"""
    eff = state._library.effective_cost(card, state.current_player().bonus())
    hand = state.current_player().tokens
    gold = hand["gold"]
    for color in GEM_COLORS:
        if eff[color] > hand[color] + gold:
            return False
        gold -= max(0, eff[color] - hand[color])
    if eff["pearl"] > hand["pearl"] + gold:
        return False
    return True


def _no_mandatory_action(state) -> bool:
    """是否没有任何可行的强制行动（触发强制补充棋盘）。"""
    r = state._rules
    p = state.current_player()
    if _non_gold_cells(state):
        return False
    if _gold_cells(state) and len(p.reserved) < r["reserve_limit"]:
        return False
    # 有可负担的卡（金字塔 + 保留）
    for tier, slots in state.pyramid.items():
        for slot, cid in enumerate(slots):
            if cid and _affordable(state, state._library.card(cid)):
                return False
    for cid in p.reserved:
        if _affordable(state, state._library.card(cid)):
            return False
    return True


# ---------------------------------------------------------------- 各行动校验

def _check_phase(state, phase):
    if state.phase == Phase.GAME_OVER:
        _err("GAME_OVER", "对局已结束")
    if state.phase != phase:
        _err("INVALID_PHASE", f"当前阶段不允许此行动（{state.phase.value}）")


def validate_use_privilege(state, action) -> None:
    _check_phase(state, "optional")
    p = state.current_player()
    if p.privileges <= 0:
        _err("NO_PRIVILEGE", "你没有特权")
    if state.privilege_used:
        _err("PRIVILEGE_USED", "本回合已使用过特权")
    if state.fill_used:
        _err("ORDER_VIOLATION", "补充棋盘后不能再使用特权（顺序：先特权后补充）")
    cell = action.get("cell")
    if not isinstance(cell, int) or not 0 <= cell < 25:
        _err("ILLEGAL_ACTION", "特权取筹码格位非法")
    if state.board[cell] is None or state.board[cell] == "gold":
        _err("ILLEGAL_ACTION", "该格无筹码或为金币")


def validate_fill_board(state, action) -> None:
    _check_phase(state, "optional")
    if state.fill_used:
        _err("FILL_USED", "本回合已补充过棋盘")
    if sum(state.bag.values()) == 0 and not _no_mandatory_action(state):
        _err("BAG_EMPTY", "布袋已空，不能补充棋盘")


def validate_take_tokens(state, action) -> None:
    _check_phase(state, "optional")
    cells = action.get("cells")
    r = state._rules
    if not isinstance(cells, list) or not 1 <= len(cells) <= r["max_take_tokens"]:
        _err("ILLEGAL_ACTION", f"必须拿取 1~{r['max_take_tokens']} 个筹码")
    if len(set(cells)) != len(cells):
        _err("ILLEGAL_ACTION", "格子重复")
    for c in cells:
        if not isinstance(c, int) or not 0 <= c < 25:
            _err("ILLEGAL_ACTION", "格位非法")
        if state.board[c] is None:
            _err("ILLEGAL_ACTION", "该格无筹码")
        if state.board[c] == "gold":
            _err("ILLEGAL_ACTION", "拿取行动不能拿金币")
    if len(cells) == 2:
        if _direction(cells[0], cells[1]) is None:
            _err("NOT_ALIGNED", "筹码必须相邻且在一条线上")
    elif len(cells) == 3:
        # 三条在同一直线：按线上顺序检查相邻方向一致
        a, b, c = cells
        d1, d2 = _direction(a, b), _direction(b, c)
        if d1 is None or d1 != d2:
            _err("NOT_ALIGNED", "筹码必须在一条不间断的直线上")
        # 中间格必须夹在两端之间
        if not _between(a, b, c):
            _err("NOT_ALIGNED", "筹码必须在一条不间断的直线上")


def _between(a, b, c) -> bool:
    """b 是否位于 a 与 c 之间（a, b, c 同行/列/斜线）。"""
    ra, ca = _cell_rc(a)
    rb, cb = _cell_rc(b)
    rc, cc = _cell_rc(c)
    dr1, dc1 = rb - ra, cb - ca
    dr2, dc2 = rc - rb, cc - cb
    return dr1 * dr2 + dc1 * dc2 > 0


def validate_reserve(state, action) -> None:
    _check_phase(state, "optional")
    r = state._rules
    p = state.current_player()
    if len(p.reserved) >= r["reserve_limit"]:
        _err("RESERVE_FULL", f"保留牌已达上限 {r['reserve_limit']} 张")
    gold_cell = action.get("gold_cell")
    if not isinstance(gold_cell, int) or state.board[gold_cell] != "gold":
        _err("NO_GOLD", "棋盘上没有金币")
    source = action.get("source")
    if source == "pyramid":
        tier = action.get("tier")
        slot = action.get("slot")
        if tier not in state.pyramid or not isinstance(slot, int):
            _err("ILLEGAL_ACTION", "保留牌格位非法")
        if not (0 <= slot < len(state.pyramid[tier])):
            _err("ILLEGAL_ACTION", "保留牌格位非法")
        if state.pyramid[tier][slot] is None:
            _err("ILLEGAL_ACTION", "该格无牌")
    elif source == "deck":
        tier = action.get("tier")
        if tier not in state.decks or not state.decks[tier]:
            _err("ILLEGAL_ACTION", "该牌库已空")
    else:
        _err("ILLEGAL_ACTION", "保留来源非法")


def validate_buy(state, action) -> None:
    _check_phase(state, "optional")
    p = state.current_player()
    source = action.get("source")
    if source == "pyramid":
        tier, slot = action.get("tier"), action.get("slot")
        if tier not in state.pyramid or not isinstance(slot, int) \
                or not (0 <= slot < len(state.pyramid[tier])):
            _err("ILLEGAL_ACTION", "购买格位非法")
        cid = state.pyramid[tier][slot]
        if cid is None:
            _err("ILLEGAL_ACTION", "该格无牌")
    elif source == "reserved":
        cid = action.get("card_id")
        if cid not in p.reserved:
            _err("ILLEGAL_ACTION", "不在你的保留牌中")
    else:
        _err("ILLEGAL_ACTION", "购买来源非法")

    card = state._library.card(cid)
    if not _affordable(state, card):
        _err("NOT_AFFORDABLE", "费用不足")

    # 支付明细校验（PAY_COLORS = 5 色 + 珍珠；金币为百搭）
    payment = action.get("payment")
    if not isinstance(payment, dict):
        _err("ILLEGAL_ACTION", "缺少支付明细")
    hand = p.tokens
    gold_used = 0
    for color in PAY_COLORS:
        part = payment.get(color, {})
        t, g = part.get("tokens", 0), part.get("gold", 0)
        if t < 0 or g < 0 or not isinstance(t, int) or not isinstance(g, int):
            _err("ILLEGAL_ACTION", "支付明细非法")
        if t > hand[color]:
            _err("PAYMENT_EXCEEDS", f"{color} 筹码支付超出持有量")
        gold_used += g
    if gold_used > hand["gold"]:
        _err("PAYMENT_EXCEEDS", "金币支付超出持有量")
    eff = state._library.effective_cost(card, p.bonus())
    for color in PAY_COLORS:
        part = payment.get(color, {})
        if part.get("tokens", 0) + part.get("gold", 0) < eff[color]:
            _err("PAYMENT_INSUFFICIENT", f"{color} 支付不足（需 {eff[color]}）")

    # 百搭卡：必须叠放到一张有奖励的卡上
    if card["bonus"] == "joker":
        target = action.get("joker_target")
        entries = {e["id"] for e in p.bought}
        if target not in entries:
            _err("ILLEGAL_ACTION", "叠放目标卡非法")
        target_card = next(e for e in p.bought if e["id"] == target)
        if target_card["bonus"] is None:
            _err("ILLEGAL_ACTION", "叠放目标必须有奖励色")

    # 能力选择
    if card["capacity"] == "take_on_board":
        color = card["bonus"]
        cells = [i for i, t in enumerate(state.board) if t == color]
        if cells:
            cell = action.get("take_cell")
            if cell not in cells:
                _err("ILLEGAL_ACTION", "拿取指示物格位非法")
    if card["capacity"] == "steal_opponent_pawn":
        opp = state.opponent(p.slot)
        stealable = [c for c in GEM_COLORS + ["pearl"] if opp.tokens[c] > 0]
        if stealable:
            color = action.get("steal_color")
            if color not in stealable:
                _err("ILLEGAL_ACTION", "偷取颜色非法或对手没有该筹码")

    # 皇家牌选择（购买后达到 3/6 皇冠时）——用购买后的皇冠数预判
    if _royal_eligible(state, p, extra_crowns=card["crowns"]):
        rc = action.get("royal_choice")
        if rc not in state.royal_pool:
            _err("ILLEGAL_ACTION", "皇家牌选择非法")
    elif action.get("royal_choice") is not None:
        _err("ILLEGAL_ACTION", "当前不满足拿取皇家牌条件")


def _royal_eligible(state, p, extra_crowns: int = 0) -> bool:
    """皇冠达到阈值时可拿皇家牌（extra_crowns: 本次购买将增加的皇冠数）。"""
    r = state._rules
    if not state.royal_pool:
        return False
    thresholds = r["royal_crown_thresholds"]
    royal_count = len(p.royal_cards)
    if royal_count >= r["max_royal_cards"]:
        return False
    return p.crowns + extra_crowns >= thresholds[royal_count]


def validate_discard(state, action) -> None:
    _check_phase(state, "discard")
    p = state.current_player()
    colors = action.get("colors")
    if not isinstance(colors, dict):
        _err("ILLEGAL_ACTION", "弃牌明细非法")
    total = sum(colors.values())
    over = p.total_tokens() - state._rules["hand_limit"]
    if total != over:
        _err("DISCARD_COUNT", f"必须恰好弃 {over} 个筹码")
    for c, n in colors.items():
        if c not in TOKEN_COLORS or n < 0 or n > p.tokens[c]:
            _err("ILLEGAL_ACTION", "弃牌明细非法")


# ---------------------------------------------------------------- 各行动执行

def apply_use_privilege(state, action) -> list:
    p = state.current_player()
    cell = action["cell"]
    color = state.board[cell]
    state.board[cell] = None
    _add_token_to_hand(state, p.slot, color)
    p.privileges -= 1
    state.privilege_pool += 1  # 放回图板上方
    state.privilege_used = True
    return [{"type": "tokens_taken", "cells": [cell], "player": p.slot}]


def apply_fill_board(state, action, rng) -> list:
    filled = _fill_board_from_bag(state, rng)
    state.fill_used = True
    events = [{"type": "board_refilled", "cells": filled}]
    events += _gain_privilege(state, state.opponent(state.current).slot)
    return events


def apply_take_tokens(state, action) -> list:
    p = state.current_player()
    cells = sorted(action["cells"])
    colors = [state.board[c] for c in cells]
    events = []
    for c in cells:
        state.board[c] = None
        _add_token_to_hand(state, p.slot, colors[cells.index(c)])
    # 3 同色 或 2 珍珠 -> 对手获特权
    if len(cells) == 3 and len(set(colors)) == 1:
        events += _gain_privilege(state, state.opponent(p.slot).slot)
    if colors.count("pearl") == 2:
        events += _gain_privilege(state, state.opponent(p.slot).slot)
    events.append({"type": "tokens_taken", "cells": cells, "player": p.slot})
    return events


def apply_reserve(state, action) -> list:
    p = state.current_player()
    gold_cell = action["gold_cell"]
    state.board[gold_cell] = None
    _add_token_to_hand(state, p.slot, "gold")
    if action["source"] == "pyramid":
        tier, slot = action["tier"], action["slot"]
        cid = state.pyramid[tier][slot]
        state.pyramid[tier][slot] = None
        _refill_pyramid(state, tier, slot)
    else:
        cid = state.decks[action["tier"]].pop()
    p.reserved.append(cid)
    return [{"type": "card_reserved", "card_id": cid, "player": p.slot}]


def apply_buy(state, action, library) -> list:
    """购买 + 卡牌能力 + 皇家牌。返回事件列表。"""
    p = state.current_player()
    events = []

    # 定位卡牌
    if action["source"] == "pyramid":
        tier, slot = action["tier"], action["slot"]
        cid = state.pyramid[tier][slot]
        state.pyramid[tier][slot] = None
        _refill_pyramid(state, tier, slot)
    else:
        cid = action["card_id"]
        p.reserved.remove(cid)
    card = library.card(cid)

    # 支付
    payment = action["payment"]
    for color in PAY_COLORS:
        part = payment.get(color, {})
        t, g = part.get("tokens", 0), part.get("gold", 0)
        p.tokens[color] -= t
        if g:
            p.tokens["gold"] -= g
            state.bag["gold"] += g
        if t:
            state.bag[color] += t

    # 入账（百搭卡记录叠放目标，奖励色取目标卡颜色）
    if card["bonus"] == "joker":
        target = next(e for e in p.bought if e["id"] == action["joker_target"])
        bonus, stacked_on = target["bonus"], target["id"]
    else:
        bonus, stacked_on = card["bonus"], None
    p.bought.append({
        "id": cid, "bonus": bonus, "bonus_number": card["bonus_number"],
        "points": card["points"], "stacked_on": stacked_on,
        "crowns": card["crowns"], "capacity": card["capacity"],
    })
    p.points += card["points"]
    p.crowns += card["crowns"]
    events.append({"type": "card_bought", "card_id": cid, "player": p.slot})

    # 卡牌能力
    events += _resolve_capacity(state, card, action, p.slot)

    # 皇家牌
    if _royal_eligible(state, p):
        rc = action["royal_choice"]
        royal = library.royal(rc)
        state.royal_pool.remove(rc)
        p.royal_cards.append(rc)
        p.points += royal["points"]
        events.append({"type": "royal_taken", "card_id": rc, "player": p.slot})
        events += _resolve_capacity(state, royal, action, p.slot, is_royal=True)

    return events


def _resolve_capacity(state, card, action, slot, is_royal=False) -> list:
    """结算卡牌/皇家牌能力（replay/take_on_board/take_priviledge/steal）。"""
    events = []
    capacity = card["capacity"]
    if capacity is None:
        return events
    p = state.player(slot)
    if capacity == "replay":
        state.replay_pending = True
        events.append({"type": "replay", "player": slot})
    elif capacity == "take_on_board":
        color = card["bonus"]
        cell = action.get("take_cell")
        if cell is not None and state.board[cell] == color:
            state.board[cell] = None
            _add_token_to_hand(state, slot, color)
            events.append({"type": "tokens_taken", "cells": [cell], "player": slot})
    elif capacity == "take_priviledge":
        events += _gain_privilege(state, slot)
    elif capacity == "steal_opponent_pawn":
        color = action.get("royal_steal_color" if is_royal else "steal_color")
        opp = state.opponent(slot)
        if color and opp.tokens.get(color, 0) > 0:
            opp.tokens[color] -= 1
            _add_token_to_hand(state, slot, color)
            events.append({"type": "tokens_stolen", "color": color, "from": opp.slot})
    return events


def validate_concede(state, action) -> None:
    """认输：对局进行中即可，任意玩家随时可认输。"""
    if state.phase == Phase.GAME_OVER:
        _err("GAME_OVER", "对局已结束")


def apply_concede(state, slot: int) -> list:
    state.winner = state.opponent(slot).slot
    state.win_reason = "concede"
    state.phase = Phase.GAME_OVER
    return [{"type": "game_over", "winner": state.winner, "reason": "concede"}]


# ---------------------------------------------------------------- 回合流转

def finish_turn(state) -> list:
    """强制行动/弃牌完成后：判胜负 -> 换人或额外回合。"""
    events = []
    result = check_win(state)
    if result:
        state.winner, state.win_reason = result
        state.phase = Phase.GAME_OVER
        events.append({"type": "game_over", "winner": result[0], "reason": result[1]})
        return events
    if state.replay_pending:
        state.replay_pending = False
        state.privilege_used = False
        state.fill_used = False
        state.phase = Phase.OPTIONAL
        events.append({"type": "turn_changed", "slot": state.current, "replay": True})
        return events
    state.current = 1 - state.current
    state.turn += 1
    state.privilege_used = False
    state.fill_used = False
    state.phase = Phase.OPTIONAL
    events.append({"type": "turn_changed", "slot": state.current})
    return events
