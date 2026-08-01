"""开局与随机性确定性。"""
from engine.game import Game
from engine.types import Phase


def test_initial_state(game):
    s = game.state
    # 25 格全满
    assert len(s.board) == 25 and all(s.board)
    # 金字塔 5/4/3，牌库 25/20/10
    assert [len(s.pyramid[t]) for t in (1, 2, 3)] == [5, 4, 3]
    assert all(all(s.pyramid[t]) for t in (1, 2, 3))
    assert [len(s.decks[t]) for t in (1, 2, 3)] == [25, 20, 10]
    # 特权：后手 1 个，先手 0，池 2
    assert s.players[0].privileges == 0
    assert s.players[1].privileges == 1
    assert s.privilege_pool == 2
    # 皇家牌 4 张可用
    assert len(s.royal_pool) == 4
    # 先手行动、可选阶段
    assert s.current == 0 and s.phase == Phase.OPTIONAL
    # 双方手牌为空
    assert all(v == 0 for v in s.players[0].tokens.values())
    assert all(v == 0 for v in s.players[1].tokens.values())


def test_same_seed_same_game(library):
    a = Game(library, seed=7).state
    b = Game(library, seed=7).state
    c = Game(library, seed=8).state
    assert a.board == b.board
    assert a.pyramid == b.pyramid
    assert a.decks == b.decks
    assert a.royal_pool == b.royal_pool
    assert a.board != c.board  # 不同种子大概率不同


def test_state_roundtrip(game):
    s = game.state
    d = s.to_dict(0)
    # 视角字段
    assert d["phase"] == "optional"
    assert len(d["players"]) == 2
    # 保留牌数量字段
    assert d["players"][0]["reserved_count"] == 0


def test_board_full_with_all_token_types(game):
    """25 格 = 五色×4 + 珍珠×2 + 金币×3。"""
    s = game.state
    counts = {}
    for t in s.board:
        counts[t] = counts.get(t, 0) + 1
    assert counts == {"white": 4, "blue": 4, "green": 4, "red": 4,
                      "black": 4, "pearl": 2, "gold": 3}
