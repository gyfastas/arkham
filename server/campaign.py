"""Campaign state management: XP tracking, deck upgrades between scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CampaignState:
    """Persistent state across scenarios in a campaign."""

    investigator_id: str
    campaign_id: str = ""  # e.g. "night_of_the_zealot", "the_dunwich_legacy"
    scenario_index: int = 0  # Which scenario in the campaign we're on

    xp: int = 0  # Available XP to spend
    xp_earned: int = 0  # Total XP earned across all scenarios
    xp_spent: int = 0  # Total XP spent on upgrades

    deck: list[str] = field(default_factory=list)  # Current deck card IDs
    victory_display: list[str] = field(default_factory=list)  # Card IDs in victory display

    trauma_physical: int = 0
    trauma_mental: int = 0

    def earn_xp_from_victory(self, card_database: dict[str, Any]) -> int:
        """Calculate and add XP from victory display cards.

        Args:
            card_database: card_id -> card data dict (must have 'victory' field)

        Returns:
            XP earned this scenario
        """
        earned = 0
        for card_id in self.victory_display:
            card = card_database.get(card_id)
            if card:
                earned += card.get("victory", 0)
        self.xp += earned
        self.xp_earned += earned
        return earned

    def add_scenario_bonus_xp(self, bonus: int) -> None:
        """Add bonus XP from scenario resolution."""
        self.xp += bonus
        self.xp_earned += bonus

    @staticmethod
    def card_purchase_cost(card_level: int) -> int:
        """Cost to buy a new card. Level 0 = free in initial build, 1 XP otherwise."""
        return max(card_level, 1)

    @staticmethod
    def card_upgrade_cost(old_level: int, new_level: int) -> int:
        """Cost to upgrade a card: difference in levels (min 1)."""
        return max(new_level - old_level, 1)

    def can_purchase(self, card_level: int) -> bool:
        """Check if player can afford to purchase a card."""
        return self.xp >= self.card_purchase_cost(card_level)

    def can_upgrade(self, old_level: int, new_level: int) -> bool:
        """Check if player can afford to upgrade a card."""
        return self.xp >= self.card_upgrade_cost(old_level, new_level)

    def purchase_card(self, card_id: str, card_level: int) -> bool:
        """Purchase a new card for the deck. Returns True if successful."""
        cost = self.card_purchase_cost(card_level)
        if self.xp < cost:
            return False
        self.xp -= cost
        self.xp_spent += cost
        self.deck.append(card_id)
        return True

    def upgrade_card(self, old_card_id: str, new_card_id: str,
                     old_level: int, new_level: int) -> bool:
        """Upgrade a card in the deck: swap old for new, pay XP difference."""
        cost = self.card_upgrade_cost(old_level, new_level)
        if self.xp < cost:
            return False
        if old_card_id not in self.deck:
            return False
        self.xp -= cost
        self.xp_spent += cost
        idx = self.deck.index(old_card_id)
        self.deck[idx] = new_card_id
        return True

    def remove_card(self, card_id: str) -> bool:
        """Remove a card from the deck (free action between scenarios)."""
        if card_id in self.deck:
            self.deck.remove(card_id)
            return True
        return False

    def apply_trauma(self, physical: int = 0, mental: int = 0) -> None:
        """Apply trauma from scenario defeat/resolution."""
        self.trauma_physical += physical
        self.trauma_mental += mental

    def advance_scenario(self) -> None:
        """Move to next scenario in campaign. Clears victory display."""
        self.scenario_index += 1
        self.victory_display.clear()

    def to_dict(self) -> dict:
        return {
            "investigator_id": self.investigator_id,
            "campaign_id": self.campaign_id,
            "scenario_index": self.scenario_index,
            "xp": self.xp,
            "xp_earned": self.xp_earned,
            "xp_spent": self.xp_spent,
            "deck": list(self.deck),
            "victory_display": list(self.victory_display),
            "trauma_physical": self.trauma_physical,
            "trauma_mental": self.trauma_mental,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CampaignState:
        return cls(
            investigator_id=data["investigator_id"],
            campaign_id=data.get("campaign_id", ""),
            scenario_index=data.get("scenario_index", 0),
            xp=data.get("xp", 0),
            xp_earned=data.get("xp_earned", 0),
            xp_spent=data.get("xp_spent", 0),
            deck=list(data.get("deck", [])),
            victory_display=list(data.get("victory_display", [])),
            trauma_physical=data.get("trauma_physical", 0),
            trauma_mental=data.get("trauma_mental", 0),
        )


def load_encounter_card_victory_values() -> dict[str, int]:
    """Load victory values from all encounter card JSONs.

    Returns: card_id -> victory value (only cards with victory > 0)
    """
    result: dict[str, int] = {}
    enc_dir = PROJECT_ROOT / "data" / "encounter_cards"
    if not enc_dir.exists():
        return result

    for p in enc_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        # Encounter card files: top-level dict with "cards" array, or a list
        cards = []
        if isinstance(data, list):
            cards = data
        elif isinstance(data, dict):
            if "cards" in data:
                cards = data["cards"]
            else:
                cards = [data]

        for card in cards:
            if not isinstance(card, dict):
                continue
            card_id = card.get("id", "")
            # victory can be top-level or nested in stats
            victory = card.get("victory") or 0
            stats = card.get("stats")
            if isinstance(stats, dict):
                victory = stats.get("victory") or victory
            if card_id and victory > 0:
                result[card_id] = victory

    return result
