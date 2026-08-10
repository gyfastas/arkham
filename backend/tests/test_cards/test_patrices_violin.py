"""Tests for Patrice's Violin (Level 0)."""

from backend.cards.neutral.patrices_violin_lv0 import PatricesViolin
from backend.models.state import CardInstance
from backend.tests.conftest import make_investigator_data


def _equip(game, inv_id="test_investigator"):
    inv = game.state.get_investigator(inv_id)
    ci = CardInstance(
        instance_id="violin_1", card_id="patrices_violin_lv0",
        owner_id=inv_id, controller_id=inv_id,
    )
    game.state.cards_in_play["violin_1"] = ci
    inv.play_area.append("violin_1")
    impl = PatricesViolin("violin_1")
    impl.register(game.event_bus, "violin_1")
    return impl


class TestPatricesViolin:
    def test_gain_resource(self, game):
        """丢1手牌并横置：同地点调查员获得1资源。"""
        impl = _equip(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["card_a", "card_b"]
        resources_before = inv.resources

        ok = impl.activate(
            game.state, "test_investigator",
            discard_card_id="card_a", effect="resource",
        )
        assert ok is True
        assert inv.resources == resources_before + 1
        assert "card_a" in inv.discard
        assert inv.hand == ["card_b"]
        inst = game.state.get_card_instance("violin_1")
        assert inst.exhausted is True

    def test_draw_card(self, game):
        """效果可选抽1张牌。"""
        impl = _equip(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["card_a"]
        inv.deck = ["card_z"]

        ok = impl.activate(game.state, "test_investigator", effect="draw")
        assert ok is True
        assert inv.hand == ["card_z"]
        assert inv.deck == []

    def test_exhausted_cannot_activate_twice(self, game):
        impl = _equip(game)
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["card_a", "card_b"]
        assert impl.activate(game.state, "test_investigator") is True
        assert impl.activate(game.state, "test_investigator") is False

    def test_target_must_be_at_same_location(self, game):
        """目标必须在同一地点。"""
        impl = _equip(game)
        other_data = make_investigator_data(id="other_inv", name="Other")
        game.register_card_data(other_data)
        game.add_investigator("other_inv", other_data, starting_location="nowhere")
        inv = game.state.get_investigator("test_investigator")
        inv.hand = ["card_a"]

        ok = impl.activate(
            game.state, "test_investigator",
            target_investigator_id="other_inv", effect="resource",
        )
        assert ok is False
        assert "card_a" in inv.hand  # 未支付费用
