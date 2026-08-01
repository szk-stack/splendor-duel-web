"""测试辅助：把目标卡放进展示区、发牌、生成购买行动。"""
import pytest


def show(game, card_id):
    """把指定卡牌放到 1 级展示区第 0 槽（替换原卡，测试专用）。"""
    s = game.state
    s.pyramid[1][0] = card_id
    return 1, 0


def give_hand(p, **tokens):
    for c, n in tokens.items():
        p.tokens[c] += n


def pay_for(game, card_id):
    card = game.library.card(card_id)
    return {c: {"tokens": n, "gold": 0} for c, n in card["cost"].items() if n}


def buy_displayed(game, slot, card_id, **extra):
    """购买已由 show() 放到 1级0槽 的卡。"""
    tier, slot_idx = show(game, card_id)
    action = {"kind": "buy", "source": "pyramid", "tier": tier, "slot": slot_idx,
              "payment": pay_for(game, card_id)}
    action.update(extra)
    return action


def take_one(game, slot):
    """拿取一个仍占位的非金币格（多次调用不冲突）。"""
    cell = next(i for i, t in enumerate(game.state.board) if t not in (None, "gold"))
    game.step(slot, {"kind": "take_tokens", "cells": [cell]})
