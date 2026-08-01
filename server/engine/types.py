"""引擎基础类型：筹码颜色、阶段、能力。"""
from enum import Enum

# 宝石五色 + 珍珠 + 金币。顺序即序列化字段顺序，冻结。
GEM_COLORS = ["white", "blue", "green", "red", "black"]
TOKEN_COLORS = GEM_COLORS + ["pearl", "gold"]


class Phase(str, Enum):
    OPTIONAL = "optional"    # 可选行动阶段（用特权/补充棋盘，或直接进入强制行动）
    MANDATORY = "mandatory"  # 必须执行一个强制行动
    DISCARD = "discard"      # 回合结束，手牌>10 必须弃牌
    GAME_OVER = "game_over"


# 卡牌能力，字段名与 data/*.json 保持一致（take_priviledge 为来源拼写，冻结）
CAPACITIES = ("replay", "take_on_board", "take_priviledge", "steal_opponent_pawn")


class EngineError(Exception):
    """引擎错误基类。"""


class InvalidAction(EngineError):
    """行动非法。code 为面向客户端的错误码。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
