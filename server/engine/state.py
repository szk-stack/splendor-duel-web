"""游戏状态：GameState / PlayerState，手写序列化（字段名冻结）。"""
from dataclasses import dataclass, field

from .types import Phase, GEM_COLORS, TOKEN_COLORS


@dataclass
class PlayerState:
    slot: int
    nickname: str = ""
    # 手牌筹码（含金币）
    tokens: dict = field(default_factory=lambda: {c: 0 for c in TOKEN_COLORS})
    privileges: int = 0
    points: int = 0
    crowns: int = 0
    # 已购买卡牌记录：[{id, bonus, bonus_number, points, stacked_on}]
    # bonus: 有效奖励色（百搭卡为复制色）；stacked_on: 叠放目标卡 id 或 None
    bought: list = field(default_factory=list)
    reserved: list = field(default_factory=list)  # 保留牌 id 列表（含盲保留）
    royal_cards: list = field(default_factory=list)  # 已获皇家牌 id 列表

    def total_tokens(self) -> int:
        return sum(self.tokens.values())

    def bonus(self) -> dict:
        """奖励统计：color -> bonus_number 合计。百搭卡按叠放目标卡的颜色计入。"""
        result = {c: 0 for c in GEM_COLORS}
        for entry in self.bought:
            # 灰卡（bonus=None）无奖励；其余（含已复制的百搭卡）计入
            if entry["bonus"] is not None:
                result[entry["bonus"]] += entry["bonus_number"]
        return result

    def points_by_bonus_color(self) -> dict:
        """各奖励色的分数（同色胜利用）。百搭卡分数计入其复制色。"""
        result = {c: 0 for c in GEM_COLORS}
        for entry in self.bought:
            if entry["bonus"] is not None:
                result[entry["bonus"]] += entry["points"]
        return result

    def to_dict(self, viewer_slot: int, library) -> dict:
        is_owner = viewer_slot == self.slot
        return {
            "slot": self.slot,
            "nickname": self.nickname,
            "tokens": dict(self.tokens),
            "privileges": self.privileges,
            "points": self.points,
            "crowns": self.crowns,
            "bought": self.bought,
            "royal_cards": list(self.royal_cards),
            # 保留牌：本人可见卡牌明细，对手只见数量
            "reserved": [_card_dict(library.card(cid)) for cid in self.reserved] if is_owner else [],
            "reserved_count": len(self.reserved),
        }

    @staticmethod
    def from_dict(d: dict) -> "PlayerState":
        p = PlayerState(slot=d["slot"])
        p.nickname = d.get("nickname", "")
        p.tokens = dict(d["tokens"])
        p.privileges = d["privileges"]
        p.points = d["points"]
        p.crowns = d["crowns"]
        p.bought = [dict(e) for e in d["bought"]]
        p.reserved = list(d["reserved"])
        p.royal_cards = list(d.get("royal_cards", []))
        return p


def _card_dict(card: dict) -> dict:
    """卡牌对外数据（不含内部字段）。"""
    return {
        "id": card["id"],
        "level": card["level"],
        "points": card["points"],
        "bonus": card["bonus"],
        "bonus_number": card["bonus_number"],
        "crowns": card["crowns"],
        "capacity": card["capacity"],
        "cost": dict(card["cost"]),
    }


def _royal_dict(royal: dict) -> dict:
    """皇家牌对外数据。"""
    return {"id": royal["id"], "points": royal["points"], "capacity": royal["capacity"]}


@dataclass
class GameState:
    seed: int
    # 5x5 棋盘，25 格，每格一个筹码颜色或 None（索引即格位）
    board: list = field(default_factory=lambda: [None] * 25)
    # 布袋：颜色 -> 数量（开局为空，花掉的筹码进入布袋）
    bag: dict = field(default_factory=lambda: {c: 0 for c in TOKEN_COLORS})
    # 金字塔展示区：tier -> 固定长度槽位（1级5/2级4/3级3），None=空位
    pyramid: dict = field(default_factory=lambda: {1: [None] * 5, 2: [None] * 4, 3: [None] * 3})
    # 牌库：tier -> card id 列表（牌库顶 = 列表末尾）
    decks: dict = field(default_factory=lambda: {1: [], 2: [], 3: []})
    # 可用皇家牌 id 列表（正面朝上，公开）
    royal_pool: list = field(default_factory=list)
    # 特权池（图板上方）：开局 3 个
    privilege_pool: int = 3
    players: list = field(default_factory=list)
    current: int = 0
    phase: Phase = Phase.OPTIONAL
    turn: int = 0
    # 本回合可选行动标记
    privilege_used: bool = False
    fill_used: bool = False
    replay_pending: bool = False
    winner: int = None
    win_reason: str = None
    # 运行时附加（不序列化）：规则与卡牌库，由 Game 创建时挂载
    _rules: dict = field(default_factory=dict, repr=False)
    _library: object = None

    def player(self, slot: int) -> PlayerState:
        return self.players[slot]

    def current_player(self) -> PlayerState:
        return self.players[self.current]

    def opponent(self, slot: int) -> PlayerState:
        return self.players[1 - slot]

    def to_dict(self, viewer_slot: int) -> dict:
        """序列化给指定玩家视角（保留牌信息按视角隐藏）。"""
        library = self._library
        return {
            "seed": self.seed,
            "board": list(self.board),
            # 金字塔展示区给出完整卡牌数据（公开）
            "pyramid": {str(t): [(_card_dict(library.card(c)) if c else None) for c in slots]
                        for t, slots in self.pyramid.items()},
            "deck_sizes": {str(t): len(cards) for t, cards in self.decks.items()},
            "royal_pool": [_royal_dict(library.royal(c)) for c in self.royal_pool],
            "players": [p.to_dict(viewer_slot, library) for p in self.players],
            "current": self.current,
            "phase": self.phase.value,
            "turn": self.turn,
            "privilege_used": self.privilege_used,
            "fill_used": self.fill_used,
            "replay_pending": self.replay_pending,
            "winner": self.winner,
            "win_reason": self.win_reason,
        }

    @staticmethod
    def from_dict(d: dict) -> "GameState":
        s = GameState(seed=d["seed"])
        s.board = list(d["board"])
        s.bag = dict(d["bag"])
        s.pyramid = {int(t): list(slots) for t, slots in d["pyramid"].items()}
        s.decks = {int(t): list(cards) for t, cards in d["decks"].items()}
        s.royal_pool = list(d["royal_pool"])
        s.privilege_pool = d.get("privilege_pool", 3)
        s.players = [PlayerState.from_dict(p) for p in d["players"]]
        s.current = d["current"]
        s.phase = Phase(d["phase"])
        s.turn = d["turn"]
        s.privilege_used = d["privilege_used"]
        s.fill_used = d["fill_used"]
        s.replay_pending = d["replay_pending"]
        s.winner = d["winner"]
        s.win_reason = d["win_reason"]
        return s
