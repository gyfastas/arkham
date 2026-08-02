"""Tests for campaign persistence, deck-diff upgrade costs, and chaos bag difficulty."""

import pytest

from backend.models.chaos import build_bag_tokens, bag_summary
from backend.models.enums import ChaosTokenType
from server.campaign import (
    CampaignState,
    campaign_scenarios,
    list_campaigns,
    load_campaign,
    new_campaign,
)


class TestChaosBagDifficulty:
    @pytest.mark.parametrize("difficulty,total", [
        ("easy", 15), ("standard", 16), ("hard", 17), ("expert", 18),
    ])
    def test_official_token_counts_core(self, difficulty, total):
        tokens = build_bag_tokens("core", difficulty)
        assert len(tokens) == total
        assert tokens.count(ChaosTokenType.AUTO_FAIL) == 1
        assert tokens.count(ChaosTokenType.ELDER_SIGN) == 1
        assert tokens.count(ChaosTokenType.SKULL) == 2

    def test_standard_has_one_minus3(self):
        tokens = build_bag_tokens("core", "standard")
        assert tokens.count(ChaosTokenType.MINUS_3) == 1

    def test_dunwich_uses_elder_thing_not_tablet(self):
        tokens = build_bag_tokens("dunwich_legacy", "standard")
        assert ChaosTokenType.ELDER_THING in tokens
        assert ChaosTokenType.TABLET not in tokens

    def test_unknown_campaign_falls_back(self):
        tokens = build_bag_tokens("nonexistent", "standard")
        assert len(tokens) == 16  # core standard fallback

    def test_bag_summary(self):
        s = bag_summary("core", "hard")
        assert s["total"] == 17
        assert s["tokens"]["-5"] == 1


class TestCampaignPersistence:
    def test_new_save_load_roundtrip(self, tmp_path, monkeypatch):
        import server.campaign as camp_mod
        monkeypatch.setattr(camp_mod, "CAMPAIGN_SAVE_DIR", tmp_path)

        camp = new_campaign("core", "daisy_walker", "hard", ["card_x"] * 30)
        assert camp.scenario_index == 0
        assert camp.xp == 0
        assert camp.difficulty == "hard"
        assert camp.current_scenario_id() == "the_gathering"

        loaded = load_campaign(camp.save_id)
        assert loaded is not None
        assert loaded.investigator_id == "daisy_walker"
        assert loaded.deck == ["card_x"] * 30

        saves = list_campaigns()
        assert len(saves) == 1
        assert saves[0]["campaign_name_cn"] == "狂热者之夜"
        assert saves[0]["scenario_total"] == 3

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        import server.campaign as camp_mod
        monkeypatch.setattr(camp_mod, "CAMPAIGN_SAVE_DIR", tmp_path)
        assert load_campaign("nope") is None

    def test_advance_and_complete(self):
        camp = CampaignState(investigator_id="inv", campaign_id="core")
        assert not camp.is_complete()
        camp.advance_scenario()
        assert camp.current_scenario_id() == "the_midnight_masks"
        camp.advance_scenario()
        camp.advance_scenario()
        assert camp.is_complete()
        assert camp.current_scenario_id() == ""


class TestDeckDiffUpgrade:
    class FakeCard:
        def __init__(self, name, level):
            self.name = name
            self.level = level

    def _db(self):
        return {
            "deduction_lv0": self.FakeCard("Deduction", 0),
            "deduction_lv2": self.FakeCard("Deduction", 2),
            "magnifying_glass_lv0": self.FakeCard("Magnifying Glass", 0),
            "magnifying_glass_lv1": self.FakeCard("Magnifying Glass", 1),
            "flashlight_lv0": self.FakeCard("Flashlight", 0),
            "guts_lv0": self.FakeCard("Guts", 0),
        }

    def _camp(self):
        deck = ["deduction_lv0", "magnifying_glass_lv0", "flashlight_lv0"] + ["guts_lv0"] * 27
        return CampaignState(investigator_id="inv", campaign_id="core", deck=deck, xp=10)

    def test_upgrade_cost_is_level_difference(self):
        camp = self._camp()
        new_deck = ["deduction_lv2", "magnifying_glass_lv0", "flashlight_lv0"] + ["guts_lv0"] * 27
        cost, _ = camp.deck_change_cost(new_deck, self._db())
        assert cost == 2

    def test_new_level0_card_costs_1(self):
        camp = self._camp()
        # swap one guts for a second flashlight (new card purchase)
        new_deck = ["deduction_lv0", "magnifying_glass_lv0", "flashlight_lv0", "flashlight_lv0"] + ["guts_lv0"] * 26
        cost, _ = camp.deck_change_cost(new_deck, self._db())
        assert cost == 1

    def test_removal_is_free(self):
        camp = self._camp()
        # replace flashlight with another guts (pure swap of lv0 for lv0 →
        # flashlight removed (free), guts added (1 XP purchase))
        new_deck = ["deduction_lv0", "magnifying_glass_lv0"] + ["guts_lv0"] * 28
        cost, _ = camp.deck_change_cost(new_deck, self._db())
        assert cost == 1  # only the new guts copy costs

    def test_apply_rejects_wrong_size(self):
        camp = self._camp()
        ok, msg, _ = camp.apply_deck_change(["guts_lv0"] * 29, self._db())
        assert not ok
        assert "30" in msg

    def test_apply_rejects_insufficient_xp(self):
        camp = self._camp()
        camp.xp = 1
        new_deck = ["deduction_lv2", "magnifying_glass_lv0", "flashlight_lv0"] + ["guts_lv0"] * 27
        ok, msg, cost = camp.apply_deck_change(new_deck, self._db())
        assert not ok
        assert cost == 2

    def test_apply_success_deducts_xp(self):
        camp = self._camp()
        new_deck = ["deduction_lv2", "magnifying_glass_lv1", "flashlight_lv0"] + ["guts_lv0"] * 27
        ok, _, cost = camp.apply_deck_change(new_deck, self._db())
        assert ok
        assert cost == 3  # 2 (deduction 0→2) + 1 (magnifying 0→1)
        assert camp.xp == 7
        assert camp.xp_spent == 3
        assert camp.deck == new_deck


class TestCampaignScenarios:
    def test_core_order(self):
        assert campaign_scenarios("core") == [
            "the_gathering", "the_midnight_masks", "the_devourer_below",
        ]

    def test_dunwich_count(self):
        assert len(campaign_scenarios("dunwich_legacy")) == 8
