"""Campaign state management: XP tracking, deck upgrades between scenarios.

Persistence: each campaign is stored as JSON under saves/campaigns/.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN_SAVE_DIR = PROJECT_ROOT / "saves" / "campaigns"


@dataclass
class CampaignState:
    """Persistent state across scenarios in a campaign."""

    investigator_id: str
    campaign_id: str = ""  # e.g. "core", "dunwich_legacy"
    scenario_index: int = 0  # Which scenario in the campaign we're on
    save_id: str = ""
    difficulty: str = "standard"

    xp: int = 0  # Available XP to spend
    xp_earned: int = 0  # Total XP earned across all scenarios
    xp_spent: int = 0  # Total XP spent on upgrades

    deck: list[str] = field(default_factory=list)  # Current deck card IDs
    victory_display: list[str] = field(default_factory=list)  # Card IDs in victory display

    trauma_physical: int = 0
    trauma_mental: int = 0

    # --- chapter helpers -------------------------------------------------

    def current_scenario_id(self) -> str:
        scenarios = campaign_scenarios(self.campaign_id)
        if 0 <= self.scenario_index < len(scenarios):
            return scenarios[self.scenario_index]
        return ""

    def is_complete(self) -> bool:
        return self.scenario_index >= len(campaign_scenarios(self.campaign_id))

    # --- XP ---------------------------------------------------------------

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

    # --- deck diff upgrade (server-authoritative) --------------------------

    def deck_change_cost(
        self, new_deck: list[str], card_db: dict[str, Any]
    ) -> tuple[int, list[str]]:
        """Compute the XP cost of transforming self.deck into new_deck.

        Official rules: upgrading a card to a higher-level version of the
        same card costs the level difference (min 1); buying a new card
        costs its level (min 1, i.e. level-0 cards cost 1 XP); removing
        cards is free.

        Returns (total_cost, notes).
        """
        from collections import Counter

        removed = Counter(self.deck) - Counter(new_deck)
        added = Counter(new_deck) - Counter(self.deck)

        def _name(cid: str) -> str:
            cd = card_db.get(cid)
            return getattr(cd, "name", None) or (cd.get("name") if isinstance(cd, dict) else None) or cid

        def _level(cid: str) -> int:
            cd = card_db.get(cid)
            if cd is None:
                return 0
            return int(getattr(cd, "level", None) or (cd.get("level") if isinstance(cd, dict) else 0) or 0)

        # Pool of removed cards available for upgrade pairing, by name
        removed_by_name: dict[str, list[str]] = {}
        for cid, n in removed.items():
            removed_by_name.setdefault(_name(cid), []).extend([cid] * n)

        total = 0
        notes: list[str] = []
        for cid, n in added.items():
            name = _name(cid)
            new_lv = _level(cid)
            for _ in range(n):
                pool = removed_by_name.get(name) or []
                if pool:
                    old_cid = pool.pop()
                    old_lv = _level(old_cid)
                    cost = self.card_upgrade_cost(old_lv, new_lv)
                    notes.append(f"{name} Lv{old_lv}→Lv{new_lv}: {cost} XP")
                else:
                    cost = self.card_purchase_cost(new_lv)
                    notes.append(f"{name}: {cost} XP")
                total += cost
        return total, notes

    def apply_deck_change(
        self, new_deck: list[str], card_db: dict[str, Any], *, deck_size: int = 30
    ) -> tuple[bool, str, int]:
        """Validate and apply a deck edit between scenarios.

        Returns (ok, message, cost).
        """
        if len(new_deck) != deck_size:
            return False, f"牌组必须为 {deck_size} 张（当前 {len(new_deck)}）", 0
        unknown = [cid for cid in new_deck if card_db.get(cid) is None]
        if unknown:
            return False, f"未知卡牌: {unknown[0]}", 0
        cost, notes = self.deck_change_cost(new_deck, card_db)
        if cost > self.xp:
            return False, f"经验不足：需要 {cost} XP，当前 {self.xp} XP", cost
        self.xp -= cost
        self.xp_spent += cost
        self.deck = list(new_deck)
        return True, ("；".join(notes) if notes else "无变动"), cost

    def to_dict(self) -> dict:
        return {
            "save_id": self.save_id,
            "investigator_id": self.investigator_id,
            "campaign_id": self.campaign_id,
            "scenario_index": self.scenario_index,
            "difficulty": self.difficulty,
            "current_scenario_id": self.current_scenario_id(),
            "is_complete": self.is_complete(),
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
            save_id=data.get("save_id", ""),
            difficulty=data.get("difficulty", "standard"),
            xp=data.get("xp", 0),
            xp_earned=data.get("xp_earned", 0),
            xp_spent=data.get("xp_spent", 0),
            deck=list(data.get("deck", [])),
            victory_display=list(data.get("victory_display", [])),
            trauma_physical=data.get("trauma_physical", 0),
            trauma_mental=data.get("trauma_mental", 0),
        )


# ---------------------------------------------------------------------------
# Campaign scenario lists & persistence
# ---------------------------------------------------------------------------

def campaign_scenarios(campaign_id: str) -> list[str]:
    """Ordered scenario ids for a campaign, from data/scenarios/*.json."""
    scen_dir = PROJECT_ROOT / "data" / "scenarios"
    items: list[tuple[int, str]] = []
    for p in scen_dir.glob("*.json"):
        if p.name == "schema.json":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("campaign") == campaign_id:
            items.append((int(d.get("sequence") or 0), d.get("id") or p.stem))
    return [sid for _, sid in sorted(items)]


def campaign_name_cn(campaign_id: str) -> str:
    names = {"core": "狂热者之夜", "dunwich_legacy": "敦威治遗产"}
    return names.get(campaign_id, campaign_id)


def new_campaign(
    campaign_id: str, investigator_id: str, difficulty: str, deck: list[str]
) -> CampaignState:
    """Create and persist a new campaign (chapter 1, 0 XP)."""
    save_id = f"{campaign_id}_{investigator_id}_{int(time.time())}"
    state = CampaignState(
        investigator_id=investigator_id,
        campaign_id=campaign_id,
        scenario_index=0,
        save_id=save_id,
        difficulty=difficulty,
        deck=list(deck),
    )
    save_campaign(state)
    return state


def save_campaign(state: CampaignState) -> None:
    CAMPAIGN_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAMPAIGN_SAVE_DIR / f"{state.save_id}.json"
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_campaign(save_id: str) -> CampaignState | None:
    path = CAMPAIGN_SAVE_DIR / f"{save_id}.json"
    if not path.is_file():
        return None
    try:
        return CampaignState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def list_campaigns() -> list[dict]:
    """Summaries of all saved campaigns for the lobby."""
    out: list[dict] = []
    if not CAMPAIGN_SAVE_DIR.is_dir():
        return out
    for p in sorted(CAMPAIGN_SAVE_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        total = len(campaign_scenarios(d.get("campaign_id", "")))
        out.append({
            "save_id": d.get("save_id") or p.stem,
            "campaign_id": d.get("campaign_id", ""),
            "campaign_name_cn": campaign_name_cn(d.get("campaign_id", "")),
            "investigator_id": d.get("investigator_id", ""),
            "difficulty": d.get("difficulty", "standard"),
            "scenario_index": d.get("scenario_index", 0),
            "scenario_total": total,
            "current_scenario_id": d.get("current_scenario_id", ""),
            "is_complete": d.get("scenario_index", 0) >= total,
            "xp": d.get("xp", 0),
            "trauma_physical": d.get("trauma_physical", 0),
            "trauma_mental": d.get("trauma_mental", 0),
        })
    return out


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
