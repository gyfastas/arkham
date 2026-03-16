"""Integration tests for the Campaign XP system.

Tests:
- CampaignState model: creation, serialization, XP tracking
- Victory → XP conversion
- Card purchase with XP (level 0 = 1 XP, level N = N XP)
- Card upgrade cost = new_level - old_level
- Deck requirements respected across scenarios
- Initial XP=0 → only level 0 cards selectable
- list_available_cards with XP filtering
"""

import pytest
from server.campaign import CampaignState, load_encounter_card_victory_values


class TestCampaignStateModel:
    """Test CampaignState dataclass basic operations."""

    def test_initial_state(self):
        cs = CampaignState(investigator_id="daisy_walker", campaign_id="night_of_the_zealot")
        assert cs.xp == 0
        assert cs.xp_earned == 0
        assert cs.xp_spent == 0
        assert cs.deck == []
        assert cs.victory_display == []
        assert cs.trauma_physical == 0
        assert cs.trauma_mental == 0
        assert cs.scenario_index == 0

    def test_serialization_roundtrip(self):
        cs = CampaignState(
            investigator_id="daisy_walker",
            campaign_id="night_of_the_zealot",
            xp=5, xp_earned=8, xp_spent=3,
            deck=["magnifying_glass_lv0", "old_book_of_lore_lv0"],
            victory_display=["ghoul_priest"],
            trauma_physical=1, trauma_mental=0,
            scenario_index=2,
        )
        d = cs.to_dict()
        cs2 = CampaignState.from_dict(d)
        assert cs2.investigator_id == "daisy_walker"
        assert cs2.xp == 5
        assert cs2.xp_earned == 8
        assert cs2.xp_spent == 3
        assert cs2.deck == ["magnifying_glass_lv0", "old_book_of_lore_lv0"]
        assert cs2.victory_display == ["ghoul_priest"]
        assert cs2.trauma_physical == 1
        assert cs2.scenario_index == 2


class TestVictoryXP:
    """Test XP earned from victory display cards."""

    def test_earn_xp_from_victory(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.victory_display = ["ghoul_priest", "swarm_of_rats", "some_enemy"]

        # Simulate card database with victory values
        card_db = {
            "ghoul_priest": {"victory": 2},
            "swarm_of_rats": {"victory": 0},
            "some_enemy": {"victory": 1},
        }

        earned = cs.earn_xp_from_victory(card_db)
        assert earned == 3
        assert cs.xp == 3
        assert cs.xp_earned == 3

    def test_earn_xp_empty_victory(self):
        cs = CampaignState(investigator_id="daisy_walker")
        earned = cs.earn_xp_from_victory({})
        assert earned == 0
        assert cs.xp == 0

    def test_earn_xp_accumulates(self):
        cs = CampaignState(investigator_id="daisy_walker")

        # Scenario 1
        cs.victory_display = ["enemy_a"]
        cs.earn_xp_from_victory({"enemy_a": {"victory": 2}})
        assert cs.xp == 2
        assert cs.xp_earned == 2

        # Advance, scenario 2
        cs.advance_scenario()
        cs.victory_display = ["enemy_b"]
        cs.earn_xp_from_victory({"enemy_b": {"victory": 3}})
        assert cs.xp == 5
        assert cs.xp_earned == 5
        assert cs.scenario_index == 1

    def test_scenario_bonus_xp(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.add_scenario_bonus_xp(2)
        assert cs.xp == 2
        assert cs.xp_earned == 2

    def test_advance_scenario_clears_victory(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.victory_display = ["enemy_a", "enemy_b"]
        cs.advance_scenario()
        assert cs.victory_display == []
        assert cs.scenario_index == 1


class TestCardPurchase:
    """Test card purchase and upgrade cost mechanics."""

    def test_purchase_cost_level_0(self):
        # Level 0 cards cost 1 XP (not free, per user spec)
        assert CampaignState.card_purchase_cost(0) == 1

    def test_purchase_cost_level_n(self):
        assert CampaignState.card_purchase_cost(1) == 1
        assert CampaignState.card_purchase_cost(2) == 2
        assert CampaignState.card_purchase_cost(3) == 3
        assert CampaignState.card_purchase_cost(5) == 5

    def test_upgrade_cost(self):
        # Upgrade from level 0 to level 2 = 2 XP
        assert CampaignState.card_upgrade_cost(0, 2) == 2
        # Upgrade from level 1 to level 3 = 2 XP
        assert CampaignState.card_upgrade_cost(1, 3) == 2
        # Upgrade from level 0 to level 5 = 5 XP
        assert CampaignState.card_upgrade_cost(0, 5) == 5
        # Minimum cost is 1
        assert CampaignState.card_upgrade_cost(0, 0) == 1

    def test_purchase_card_success(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=5)
        assert cs.purchase_card("deduction_lv2", 2)
        assert cs.xp == 3
        assert cs.xp_spent == 2
        assert "deduction_lv2" in cs.deck

    def test_purchase_card_insufficient_xp(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=1)
        assert not cs.purchase_card("deduction_lv2", 2)
        assert cs.xp == 1
        assert cs.xp_spent == 0
        assert "deduction_lv2" not in cs.deck

    def test_upgrade_card_success(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=5)
        cs.deck = ["magnifying_glass_lv0", "deduction_lv0"]

        assert cs.upgrade_card("magnifying_glass_lv0", "magnifying_glass_lv1", 0, 1)
        assert cs.xp == 4
        assert cs.xp_spent == 1
        assert "magnifying_glass_lv1" in cs.deck
        assert "magnifying_glass_lv0" not in cs.deck

    def test_upgrade_card_not_in_deck(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=5)
        cs.deck = ["deduction_lv0"]

        assert not cs.upgrade_card("magnifying_glass_lv0", "magnifying_glass_lv1", 0, 1)
        assert cs.xp == 5

    def test_upgrade_card_insufficient_xp(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=1)
        cs.deck = ["magnifying_glass_lv0"]

        assert not cs.upgrade_card("magnifying_glass_lv0", "magnifying_glass_lv3", 0, 3)
        assert cs.xp == 1

    def test_remove_card(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.deck = ["card_a", "card_b", "card_c"]
        assert cs.remove_card("card_b")
        assert cs.deck == ["card_a", "card_c"]

    def test_remove_card_not_found(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.deck = ["card_a"]
        assert not cs.remove_card("card_z")


class TestCanAffordChecks:
    """Test can_purchase and can_upgrade checks."""

    def test_can_purchase(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=3)
        assert cs.can_purchase(0)  # cost 1
        assert cs.can_purchase(1)  # cost 1
        assert cs.can_purchase(2)  # cost 2
        assert cs.can_purchase(3)  # cost 3
        assert not cs.can_purchase(4)  # cost 4, only have 3

    def test_can_upgrade(self):
        cs = CampaignState(investigator_id="daisy_walker", xp=3)
        assert cs.can_upgrade(0, 2)  # cost 2
        assert cs.can_upgrade(0, 3)  # cost 3
        assert not cs.can_upgrade(0, 4)  # cost 4


class TestTrauma:
    """Test trauma application."""

    def test_apply_trauma(self):
        cs = CampaignState(investigator_id="daisy_walker")
        cs.apply_trauma(physical=1, mental=2)
        assert cs.trauma_physical == 1
        assert cs.trauma_mental == 2

        cs.apply_trauma(physical=1)
        assert cs.trauma_physical == 2
        assert cs.trauma_mental == 2


class TestListAvailableCardsXP:
    """Test that list_available_cards respects XP filtering."""

    def test_initial_xp_zero_only_level_zero_allowed(self):
        from server.game_session import list_available_cards
        result = list_available_cards("daisy_walker", xp_available=0)
        cards = result["cards"]

        for card in cards:
            if card["level"] == 0:
                assert card["allowed"] is True, f"{card['id']} level 0 should be allowed"
            else:
                assert card["allowed"] is False, f"{card['id']} level {card['level']} should NOT be allowed with 0 XP"

    def test_with_xp_higher_levels_unlocked(self):
        from server.game_session import list_available_cards
        result = list_available_cards("daisy_walker", xp_available=3)
        cards = result["cards"]

        for card in cards:
            if card["level"] <= 3:
                assert card["allowed"] is True, f"{card['id']} level {card['level']} should be allowed with 3 XP"
            else:
                assert card["allowed"] is False, f"{card['id']} level {card['level']} should NOT be allowed with 3 XP"


class TestCampaignWorkflow:
    """End-to-end campaign workflow test."""

    def test_full_campaign_flow(self):
        """Simulate: initial build → play scenario → earn XP → upgrade deck."""
        # Step 1: Create campaign with initial deck (all level 0)
        cs = CampaignState(
            investigator_id="daisy_walker",
            campaign_id="night_of_the_zealot",
        )
        initial_deck = [
            "magnifying_glass_lv0", "magnifying_glass_lv0",
            "old_book_of_lore_lv0", "old_book_of_lore_lv0",
            "dr_milan_christopher_lv0",
        ]
        cs.deck = list(initial_deck)
        assert cs.xp == 0

        # Step 2: Play scenario 1, defeat enemies with victory
        cs.victory_display = ["ghoul_priest"]  # victory 2
        card_db = {"ghoul_priest": {"victory": 2}}
        earned = cs.earn_xp_from_victory(card_db)
        assert earned == 2

        # Scenario bonus XP
        cs.add_scenario_bonus_xp(1)
        assert cs.xp == 3
        assert cs.xp_earned == 3

        # Step 3: Upgrade phase
        # Upgrade magnifying_glass from lv0 to lv1 (cost: 1 XP)
        assert cs.upgrade_card("magnifying_glass_lv0", "magnifying_glass_lv1", 0, 1)
        assert cs.xp == 2

        # Purchase a new level 2 card (cost: 2 XP)
        assert cs.purchase_card("deduction_lv2", 2)
        assert cs.xp == 0
        assert cs.xp_spent == 3

        # Can't afford anything more
        assert not cs.can_purchase(1)

        # Step 4: Advance to next scenario
        cs.advance_scenario()
        assert cs.scenario_index == 1
        assert cs.victory_display == []

        # Deck should reflect upgrades
        assert "magnifying_glass_lv1" in cs.deck
        assert "deduction_lv2" in cs.deck
        assert cs.deck.count("magnifying_glass_lv0") == 1  # Only one was upgraded


class TestEncounterCardVictoryValues:
    """Test loading victory values from encounter card files."""

    def test_load_dunwich_legacy_victory_values(self):
        """Dunwich legacy encounter cards should have victory values."""
        values = load_encounter_card_victory_values()
        # We know from grep that dunwich_legacy.json has many victory cards
        # At least some should be loaded
        assert len(values) > 0
        # All values should be > 0
        for card_id, v in values.items():
            assert v > 0, f"{card_id} should have positive victory"
