"""胜利判定。"""
from .types import GEM_COLORS


def check_win(state) -> tuple:
    """返回 (winner_slot, reason) 或 None。reason: points|crowns|same_color。"""
    for p in state.players:
        if p.points >= state._rules["win_points"]:
            return p.slot, "points"
        if p.crowns >= state._rules["win_crowns"]:
            return p.slot, "crowns"
        for color in GEM_COLORS:
            if p.points_by_bonus_color()[color] >= state._rules["win_same_color_points"]:
                return p.slot, f"same_color:{color}"
    return None
