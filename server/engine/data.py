"""数据加载：卡牌/皇家牌/筹码/规则 JSON 加载 + schema 校验 + CardLibrary。"""
import json
from pathlib import Path

from .types import EngineError, GEM_COLORS, TOKEN_COLORS, CAPACITIES

DATA_DIR = Path(__file__).parent / "data"

COST_COLORS = ["white", "blue", "green", "red", "black", "pearl"]


class DataError(EngineError):
    pass


def _load(name: str) -> dict:
    path = DATA_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise DataError(f"数据文件 {name} 加载失败: {e}")


def _validate_card(c, tier: int) -> None:
    if not isinstance(c, dict):
        raise DataError(f"cards_t{tier}.json 中存在非对象条目")
    for key in ("id", "points", "bonus", "bonus_number", "crowns", "capacity", "cost"):
        if key not in c:
            raise DataError(f"cards_t{tier}.json 条目 {c.get('id')} 缺少字段 {key}")
    if c["level"] != tier:
        raise DataError(f"卡 {c['id']} 的 level 与所在文件不符")
    if c["bonus"] not in (None, *GEM_COLORS, "joker"):
        raise DataError(f"卡 {c['id']} bonus 非法: {c['bonus']}")
    if c["capacity"] not in (None, *CAPACITIES):
        raise DataError(f"卡 {c['id']} capacity 非法: {c['capacity']}")
    for color in COST_COLORS:
        if color not in c["cost"] or not isinstance(c["cost"][color], int):
            raise DataError(f"卡 {c['id']} cost.{color} 非法")


def _validate_royal(r) -> None:
    for key in ("id", "points", "capacity"):
        if key not in r:
            raise DataError(f"royal_cards.json 条目缺少字段 {key}")
    if r["capacity"] not in (None, *CAPACITIES):
        raise DataError(f"皇家牌 {r['id']} capacity 非法: {r['capacity']}")


class CardLibrary:
    """卡牌库：加载全部数据文件并校验。"""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.cards: dict[str, dict] = {}     # id -> card
        self.royal_cards: dict[str, dict] = {}
        self.tokens: dict = {}
        self.rules: dict = {}
        self.load()

    def load(self) -> None:
        for tier in (1, 2, 3):
            cards = json.loads((self.data_dir / f"cards_t{tier}.json").read_text(encoding="utf-8"))
            for c in cards:
                _validate_card(c, tier)
                if c["id"] in self.cards:
                    raise DataError(f"卡牌 id 重复: {c['id']}")
                self.cards[c["id"]] = c
        royals = json.loads((self.data_dir / "royal_cards.json").read_text(encoding="utf-8"))
        for r in royals:
            _validate_royal(r)
            self.royal_cards[r["id"]] = r
        self.tokens = json.loads((self.data_dir / "tokens.json").read_text(encoding="utf-8"))
        self.rules = json.loads((self.data_dir / "rules.json").read_text(encoding="utf-8"))
        self._check_integrity()

    def _check_integrity(self) -> None:
        # 每阶展示区所需牌数 <= 该阶总牌数
        for tier, visible in self.rules["pyramid_visible"].items():
            count = sum(1 for c in self.cards.values() if c["level"] == int(tier))
            if count < visible:
                raise DataError(f"第{tier}阶牌数 {count} 少于展示需求 {visible}")
        # 无珍珠奖励
        for c in self.cards.values():
            if c["bonus"] == "pearl":
                raise DataError(f"卡 {c['id']} 奖励色为珍珠（规则不允许）")
        # take_on_board 卡的奖励色必须是五色之一
        for c in self.cards.values():
            if c["capacity"] == "take_on_board" and c["bonus"] not in GEM_COLORS:
                raise DataError(f"卡 {c['id']} 的 take_on_board 能力要求五色奖励")
        # 百搭卡的 bonus_number 恒为 1
        for c in self.cards.values():
            if c["bonus"] == "joker" and c["bonus_number"] != 1:
                raise DataError(f"卡 {c['id']} 百搭卡 bonus_number 必须为 1")

    def card(self, card_id: str) -> dict:
        if card_id not in self.cards:
            raise DataError(f"未知卡牌 id: {card_id}")
        return self.cards[card_id]

    def royal(self, card_id: str) -> dict:
        if card_id not in self.royal_cards:
            raise DataError(f"未知皇家牌 id: {card_id}")
        return self.royal_cards[card_id]

    def cards_by_tier(self, tier: int) -> list:
        return [c for c in self.cards.values() if c["level"] == tier]

    def effective_cost(self, card: dict, bonus: dict) -> dict:
        """扣除奖励后的实际费用（五色可减免，珍珠不减）。"""
        cost = card["cost"]
        eff = {}
        for color in GEM_COLORS:
            eff[color] = max(0, cost[color] - bonus.get(color, 0))
        eff["pearl"] = cost["pearl"]
        return eff


# 单例（引擎通常只用一个库）
_library = None


def get_library() -> CardLibrary:
    global _library
    if _library is None:
        _library = CardLibrary()
    return _library
