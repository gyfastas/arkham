"""Tests for Professor William Webb (Level 0 / Level 2).

官方 lv0：[反应]你成功调查时，消耗+1秘密：不发现你所在地点的线索，
改为取回弃牌堆1张[[道具]]卡，或发现连接地点1个线索。
官方 lv2：消耗+1秘密：取回弃牌堆1张[[道具]]卡；你可以改为在连接地点
发现线索。
"""

import pytest

from backend.cards.seeker.professor_william_webb_lv0 import ProfessorWilliamWebb
from backend.cards.seeker.professor_william_webb_lv2 import ProfessorWilliamWebbLv2
from backend.engine.event_bus import EventContext
from backend.engine.game import Game
from backend.models.enums import GameEvent
from backend.models.state import CardInstance
from backend.tests.conftest import (
    make_asset_data, make_investigator_data, make_location_data,
)


def _setup(card_id, impl_cls):
    g = Game(f"test_{card_id}")
    g.chaos_bag.seed(42)

    inv_data = make_investigator_data(intellect=4)
    g.register_card_data(inv_data)
    loc_a = make_location_data(id="loc_a", connections=["loc_b"])
    loc_b = make_location_data(id="loc_b", connections=["loc_a"])
    g.register_card_data(loc_a)
    g.register_card_data(loc_b)
    g.add_investigator("player", inv_data, starting_location="loc_a")
    g.add_location("loc_a", loc_a, clues=2)
    g.add_location("loc_b", loc_b, clues=1)

    g.register_card_data(make_asset_data(
        id=card_id, name="Professor William Webb", cost=3,
        traits=["ally", "miskatonic"], uses={"secretss": 3}))
    g.register_card_data(make_asset_data(
        id="magnifying_glass_lv0", name="Magnifying Glass",
        traits=["item", "tool"]))
    g.register_card_data(make_asset_data(
        id="art_student_lv0", name="Art Student", traits=["ally"]))

    inst = CardInstance(
        instance_id="inst_webb", card_id=card_id,
        owner_id="player", controller_id="player",
    )
    inst.uses = {"secretss": 3}
    g.state.cards_in_play["inst_webb"] = inst
    g.state.get_investigator("player").play_area.append("inst_webb")

    impl = impl_cls("inst_webb")
    impl.register(g.event_bus, "inst_webb")
    return g, impl


def _discover_clue(game):
    """模拟调查成功的基础发现（引擎 actions._investigate 的结算）。"""
    inv = game.state.get_investigator("player")
    loc = game.state.get_location("loc_a")
    loc.clues -= 1
    inv.clues += 1
    ctx = EventContext(
        game_state=game.state, event=GameEvent.CLUE_DISCOVERED,
        investigator_id="player", location_id="loc_a", amount=1,
    )
    game.event_bus.emit(ctx)
    return ctx


class TestProfessorWilliamWebbLv0:
    def test_returns_item_instead_of_clue(self):
        """默认分支：改为取回弃牌堆的道具卡，本地点线索返还。"""
        g, _impl = _setup("professor_william_webb_lv0", ProfessorWilliamWebb)
        inv = g.state.get_investigator("player")
        inv.discard = ["magnifying_glass_lv0"]
        inst = g.state.get_card_instance("inst_webb")
        loc_a = g.state.get_location("loc_a")

        ctx = _discover_clue(g)
        assert ctx.extra.get("webb_returned_item") == "magnifying_glass_lv0"
        assert "magnifying_glass_lv0" in inv.hand
        assert loc_a.clues == 2  # 基础发现被返还
        assert inv.clues == 0
        assert inst.exhausted is True
        assert inst.uses["secretss"] == 2

    def test_discovers_at_connecting_location_when_no_item(self):
        """弃牌堆无道具：改为在连接地点发现1个线索。"""
        g, _impl = _setup("professor_william_webb_lv0", ProfessorWilliamWebb)
        inv = g.state.get_investigator("player")
        inv.discard = ["art_student_lv0"]  # 盟友不是道具
        loc_a = g.state.get_location("loc_a")
        loc_b = g.state.get_location("loc_b")

        ctx = _discover_clue(g)
        assert ctx.extra.get("webb_connected_clue") == "loc_b"
        assert loc_a.clues == 2
        assert loc_b.clues == 0
        assert inv.clues == 1  # 在连接地点发现

    def test_no_valid_branch_no_trigger(self):
        """弃牌堆无道具且连接地点无线索：不触发不消耗。"""
        g, _impl = _setup("professor_william_webb_lv0", ProfessorWilliamWebb)
        g.state.get_location("loc_b").clues = 0
        inst = g.state.get_card_instance("inst_webb")
        loc_a = g.state.get_location("loc_a")
        inv = g.state.get_investigator("player")

        _discover_clue(g)
        assert loc_a.clues == 1  # 基础发现保留
        assert inv.clues == 1
        assert inst.exhausted is False
        assert inst.uses["secretss"] == 3


class TestProfessorWilliamWebbLv2:
    def test_returns_item_and_keeps_clue_by_default(self):
        """lv2：道具入手，本地点线索保留（"改为"为可选项，默认不选）。"""
        g, _impl = _setup("professor_william_webb_lv2", ProfessorWilliamWebbLv2)
        inv = g.state.get_investigator("player")
        inv.discard = ["magnifying_glass_lv0"]
        loc_a = g.state.get_location("loc_a")

        ctx = _discover_clue(g)
        assert ctx.extra.get("webb_returned_item") == "magnifying_glass_lv0"
        assert "magnifying_glass_lv0" in inv.hand
        assert loc_a.clues == 1  # 基础发现保留
        assert inv.clues == 1

    def test_redirect_to_connecting_location(self):
        """lv2：选择改为在连接地点发现线索。"""
        g, impl = _setup("professor_william_webb_lv2", ProfessorWilliamWebbLv2)
        inv = g.state.get_investigator("player")
        inv.discard = ["magnifying_glass_lv0"]
        impl.next_redirect = True
        loc_a = g.state.get_location("loc_a")
        loc_b = g.state.get_location("loc_b")

        ctx = _discover_clue(g)
        assert ctx.extra.get("webb_returned_item") == "magnifying_glass_lv0"
        assert ctx.extra.get("webb_connected_clue") == "loc_b"
        assert loc_a.clues == 2  # 本地点发现被改为连接地点
        assert loc_b.clues == 0
        assert inv.clues == 1

    def test_no_item_no_trigger(self):
        """lv2：弃牌堆无道具（必选分支不可用）：不触发。"""
        g, _impl = _setup("professor_william_webb_lv2", ProfessorWilliamWebbLv2)
        inst = g.state.get_card_instance("inst_webb")
        inv = g.state.get_investigator("player")
        loc_a = g.state.get_location("loc_a")

        _discover_clue(g)
        assert loc_a.clues == 1
        assert inv.clues == 1
        assert inst.exhausted is False
        assert inst.uses["secretss"] == 3
