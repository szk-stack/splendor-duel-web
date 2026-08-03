"""Game 门面：创建对局、执行行动、查询合法行动与状态。"""
import random

from . import actions
from .data import CardLibrary
from .state import GameState, PlayerState
from .types import InvalidAction, Phase, GEM_COLORS


class Game:
    def __init__(self, library: CardLibrary, seed: int, nicknames=(None, None)):
        self.library = library
        self.rng = random.Random(seed)
        self.state = self._create(seed, nicknames)

    # ------------------------------------------------------------ 创建

    def _create(self, seed: int, nicknames) -> GameState:
        rules = dict(self.library.rules)
        # spiral_order 定义在 tokens.json（棋盘数据），并入 rules 供引擎统一读取
        rules["spiral_order"] = self.library.tokens["spiral_order"]
        state = GameState(seed=seed)
        state._rules = rules
        state._library = self.library

        # 玩家（先后手与起始特权在 shuffle 完成后统一设置，保证 rng 序列与旧版一致）
        state.privilege_pool = rules["max_privileges"]
        for slot in (0, 1):
            p = PlayerState(slot=slot, nickname=nicknames[slot] or f"玩家{slot + 1}")
            state.players.append(p)

        # 筹码：全部洗入棋盘（螺旋顺序，格位即索引）
        tokens = []
        for color, n in self.library.tokens["initial"].items():
            tokens += [color] * n
        self.rng.shuffle(tokens)
        for cell, color in zip(rules["spiral_order"], tokens):
            state.board[cell] = color

        # 牌库（牌库顶 = 列表末尾）与金字塔展示区
        for tier in (1, 2, 3):
            cards = self.library.cards_by_tier(tier)
            self.rng.shuffle(cards)
            deck = [c["id"] for c in cards]
            visible = rules["pyramid_visible"][str(tier)]
            for i in range(visible):
                state.pyramid[tier][i] = deck.pop()
            state.decks[tier] = deck

        # 皇家牌池
        royal_ids = list(self.library.royal_cards.keys())
        self.rng.shuffle(royal_ids)
        state.royal_pool = royal_ids

        state.phase = Phase.OPTIONAL
        # 先后手随机（在全部 shuffle 之后消费 rng，保证牌面序列与旧版一致）；
        # 后手获起始特权（特权跟随后手，不绑定 slot）
        state.current = self.rng.choice([0, 1])
        second = 1 - state.current
        state.players[second].privileges = rules["second_player_start_privileges"]
        state.privilege_pool -= state.players[second].privileges
        return state

    # ------------------------------------------------------------ 行动入口

    def step(self, slot: int, action: dict) -> list:
        """执行一个行动。非法时抛 InvalidAction。返回事件列表。"""
        state = self.state
        kind = action.get("kind")

        # 认输不受回合限制（任意玩家随时可认输）
        if kind == "concede":
            actions.validate_concede(state, action)
            return actions.apply_concede(state, slot)

        if slot != state.current:
            raise InvalidAction("NOT_YOUR_TURN", "还没轮到你行动")

        if kind == "use_privilege":
            actions.validate_use_privilege(state, action)
            events = actions.apply_use_privilege(state, action)
        elif kind == "fill_board":
            actions.validate_fill_board(state, action)
            events = actions.apply_fill_board(state, action, self.rng)
        elif kind == "take_tokens":
            actions.validate_take_tokens(state, action)
            events = actions.apply_take_tokens(state, action)
            events += self._after_mandatory()
        elif kind == "reserve":
            actions.validate_reserve(state, action)
            events = actions.apply_reserve(state, action)
            events += self._after_mandatory()
        elif kind == "buy":
            actions.validate_buy(state, action)
            events = actions.apply_buy(state, action, self.library)
            events += self._after_mandatory()
        elif kind == "discard":
            actions.validate_discard(state, action)
            events = self._apply_discard(action)
            events += actions.finish_turn(state)
        else:
            raise InvalidAction("UNKNOWN_ACTION", f"未知行动类型: {kind}")
        return events

    def _after_mandatory(self) -> list:
        """强制行动结束后：手牌>10 进入弃牌阶段，否则结束回合。"""
        state = self.state
        if state.current_player().total_tokens() > state._rules["hand_limit"]:
            state.phase = Phase.DISCARD
            return []
        return actions.finish_turn(state)

    def _apply_discard(self, action) -> list:
        state = self.state
        p = state.current_player()
        for color, n in action["colors"].items():
            p.tokens[color] -= n
            state.bag[color] += n
        return [{"type": "tokens_discarded", "colors": dict(action["colors"])}]

    # ------------------------------------------------------------ 查询

    def legal_actions(self, slot: int) -> dict:
        """当前玩家视角的合法行动（供前端高亮/按钮）。"""
        state = self.state
        rules = state._rules
        result = {"phase": state.phase.value}
        if slot != state.current or state.phase == Phase.GAME_OVER:
            result["actions"] = []
            return result
        if state.phase == Phase.DISCARD:
            result["discard"] = {
                "over": state.current_player().total_tokens() - rules["hand_limit"],
                "hand": dict(state.current_player().tokens),
            }
            return result

        p = state.current_player()
        non_gold = actions._non_gold_cells(state)
        mandatory = self._mandatory_options()

        # 若无任何强制行动可行 -> 必须补充棋盘
        if not mandatory and not state.fill_used:
            if sum(state.bag.values()) > 0:
                result["actions"] = [{"kind": "force_fill"}]
            else:
                result["actions"] = []
            return result

        opts = []
        if (p.privileges > 0 and not state.privilege_used and not state.fill_used
                and non_gold):  # 棋盘无非金格时无格可换，不列出
            opts.append({"kind": "use_privilege", "cells": non_gold})
        if sum(state.bag.values()) > 0 and not state.fill_used:
            opts.append({"kind": "fill_board"})
        result["actions"] = opts + mandatory
        return result

    def _mandatory_options(self) -> list:
        state = self.state
        rules = state._rules
        p = state.current_player()
        opts = []

        non_gold = actions._non_gold_cells(state)
        if non_gold:
            opts.append({"kind": "take_tokens", "cells": non_gold})

        gold_cells = actions._gold_cells(state)
        # 保留行动需要金币 + 至少一张可保留的牌（展示区或牌库），否则不列为合法行动
        has_reservable = any(c for slots in state.pyramid.values() for c in slots) \
            or any(deck for deck in state.decks.values())
        if gold_cells and has_reservable and len(p.reserved) < rules["reserve_limit"]:
            opts.append({
                "kind": "reserve",
                "gold_cells": gold_cells,
                "pyramid": {str(t): [i for i, c in enumerate(slots) if c]
                            for t, slots in state.pyramid.items()},
                "decks": [t for t, deck in state.decks.items() if deck],
            })

        buyable = []
        stack_targets = [e["id"] for e in p.bought if e["bonus"] is not None]
        for tier, slots in state.pyramid.items():
            for slot, cid in enumerate(slots):
                if cid:
                    card = self.library.card(cid)
                    if actions._affordable(state, card):
                        opt = {"card": self._card_opt(card), "source": "pyramid",
                               "tier": tier, "slot": slot}
                        if card["bonus"] == "joker":
                            if not stack_targets:
                                continue
                            opt["stack_targets"] = stack_targets
                        if actions._royal_eligible(state, p, extra_crowns=card["crowns"]):
                            opt["royal_required"] = True
                        buyable.append(opt)
        for cid in p.reserved:
            card = self.library.card(cid)
            if actions._affordable(state, card):
                opt = {"card": self._card_opt(card), "source": "reserved", "card_id": cid}
                if card["bonus"] == "joker":
                    if not stack_targets:
                        continue
                    opt["stack_targets"] = stack_targets
                if actions._royal_eligible(state, p, extra_crowns=card["crowns"]):
                    opt["royal_required"] = True
                buyable.append(opt)
        if buyable:
            opts.append({"kind": "buy", "options": buyable})
        return opts

    @staticmethod
    def _card_opt(card: dict) -> dict:
        return {
            "id": card["id"], "level": card["level"], "points": card["points"],
            "bonus": card["bonus"], "bonus_number": card["bonus_number"],
            "crowns": card["crowns"], "capacity": card["capacity"],
            "cost": dict(card["cost"]),
        }

    def state_dict(self, slot: int) -> dict:
        return self.state.to_dict(slot)
