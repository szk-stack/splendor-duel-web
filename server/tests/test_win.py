"""三种胜利条件与皇家牌测试。"""
import pytest

from engine.types import InvalidAction
from helpers import show, give_hand, pay_for, buy_displayed, take_one


def set_hand(p, cost):
    """把玩家手牌精确设为卡牌费用（免去弃牌流程）。"""
    for c in p.tokens:
        p.tokens[c] = cost.get(c, 0)


def discard_down(game, slot):
    """弃到 10 个（跨颜色分摊）。"""
    s = game.state
    p = s.player(slot)
    over = p.total_tokens() - s._rules["hand_limit"]
    colors = {}
    for c in list(p.tokens):
        if over <= 0:
            break
        n = min(over, p.tokens[c])
        if n:
            colors[c] = n
        over -= n
    game.step(slot, {"kind": "discard", "colors": colors})


def test_win_by_points(game):
    s = game.state
    # 连买高分灰卡：5+6+4+4+3 = 22 分；每次购买前精确给足费用
    for cid in ("carte_58", "carte_59", "carte_61", "carte_62", "carte_63"):
        card = game.library.card(cid)
        set_hand(s.players[0], card["cost"])
        game.step(0, buy_displayed(game, 0, cid))
        if s.phase.value == "game_over":
            break
        if s.phase.value == "discard":
            discard_down(game, 0)
        if s.phase.value != "game_over":
            take_one(game, 1)  # 对手回合
    assert s.phase.value == "game_over"
    assert s.winner == 0
    assert s.win_reason == "points"


def test_win_by_crowns(game):
    s = game.state
    p = s.players[0]
    p.crowns = 7
    # 先有一张带奖励的卡（叠放目标）
    p.bought.append({"id": "carte_8", "bonus": "red", "bonus_number": 1,
                     "points": 0, "stacked_on": None})
    give_hand(p, black=8)
    action = buy_displayed(game, 0, "carte_70")  # 百搭 + 3 皇冠
    action["joker_target"] = "carte_8"
    action["royal_choice"] = s.royal_pool[0]  # 7+3=10 皇冠前已达 6 皇冠线
    game.step(0, action)
    assert s.phase.value == "game_over"
    assert s.winner == 0
    assert s.win_reason == "crowns"


def test_win_by_same_color(game):
    s = game.state
    p = s.players[0]
    p.bought.append({"id": "carte_x", "bonus": "red", "bonus_number": 1,
                     "points": 10, "stacked_on": None})
    take_one(game, 0)
    assert s.phase.value == "game_over"
    assert s.win_reason == "same_color:red"


def test_gray_cards_do_not_count_same_color(game):
    s = game.state
    p = s.players[0]
    p.bought.append({"id": "carte_34", "bonus": None, "bonus_number": 0,
                     "points": 3, "stacked_on": None})
    p.bought.append({"id": "carte_y", "bonus": "red", "bonus_number": 1,
                     "points": 9, "stacked_on": None})
    take_one(game, 0)
    assert s.phase.value != "game_over"
    assert s.current == 1  # 正常换人


def test_joker_points_count_as_copied_color(game):
    """百搭卡分数计入复制色（官方：including copy color cards）。"""
    s = game.state
    p = s.players[0]
    p.bought.append({"id": "carte_other", "bonus": "blue", "bonus_number": 1,
                     "points": 4, "stacked_on": None})
    p.bought.append({"id": "carte_z", "bonus": "blue", "bonus_number": 1,
                     "points": 6, "stacked_on": "carte_other"})
    take_one(game, 0)
    assert s.phase.value == "game_over"
    assert s.win_reason == "same_color:blue"


def test_royal_card_at_3_crowns(game):
    s = game.state
    p = s.players[0]
    p.crowns = 2
    give_hand(p, black=3)
    action = buy_displayed(game, 0, "carte_8")  # 1 皇冠 -> 3 皇冠
    # 不选皇家牌 -> 拒绝
    with pytest.raises(InvalidAction):
        game.step(0, action)
    # 指定皇家牌 -> 成功
    royal = s.royal_pool[0]
    action["royal_choice"] = royal
    game.step(0, action)
    assert royal in p.royal_cards
    assert royal not in s.royal_pool
    assert p.points == s._library.royal(royal)["points"]
    assert s.current == 1


def test_steal_capacity_no_opponent_tokens(game):
    """偷取：对手无筹码则忽略（无需指定颜色）。"""
    s = game.state
    give_hand(s.players[0], **{c: 6 for c in ("white", "blue", "green", "red", "black")})
    game.step(0, buy_displayed(game, 0, "carte_37"))  # 偷取卡，对手无筹码
    assert s.phase.value != "game_over"


def test_steal_capacity_steals_color(game):
    s = game.state
    p1 = s.players[1]
    p1.tokens["red"] = 2
    give_hand(s.players[0], **{c: 6 for c in ("white", "blue", "green", "red", "black")})
    action = buy_displayed(game, 0, "carte_37")
    action["steal_color"] = "red"
    game.step(0, action)
    assert p1.tokens["red"] == 1
    assert s.players[0].tokens["red"] == 7  # 6 基础 + 1 偷取
    # 不能偷金币
    p1.tokens["gold"] = 1
    action = buy_displayed(game, 0, "carte_37")
    action["steal_color"] = "gold"
    with pytest.raises(InvalidAction):
        game.step(0, action)


def test_take_on_board_capacity(game):
    """拿取指示物：从棋盘拿 1 个奖励色筹码。"""
    s = game.state
    give_hand(s.players[0], blue=2, green=2)
    action = buy_displayed(game, 0, "carte_9")  # 蓝2绿2, take_on_board, 红奖励
    red_cells = [i for i, t in enumerate(s.board) if t == "red"]
    if red_cells:
        action["take_cell"] = red_cells[0]
    game.step(0, action)
    p = s.players[0]
    assert p.tokens["red"] == 1
    assert s.board[red_cells[0]] is None if red_cells else True
