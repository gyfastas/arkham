"""Chaos bag implementation."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from backend.models.enums import ChaosTokenType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIFFICULTIES = ("easy", "standard", "hard", "expert")


# Fallback bag (official NOTZ Standard), used when data/chaos_bags.json is
# missing or lacks the requested campaign/difficulty.
STANDARD_BAG = [
    ChaosTokenType.PLUS_1,
    ChaosTokenType.ZERO, ChaosTokenType.ZERO, ChaosTokenType.ZERO,
    ChaosTokenType.MINUS_1, ChaosTokenType.MINUS_1, ChaosTokenType.MINUS_1,
    ChaosTokenType.MINUS_2, ChaosTokenType.MINUS_2,
    ChaosTokenType.MINUS_3,
    ChaosTokenType.SKULL, ChaosTokenType.SKULL,
    ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET,
    ChaosTokenType.AUTO_FAIL,
    ChaosTokenType.ELDER_SIGN,
]

_BAG_DATA: dict | None = None


def load_chaos_bag_data() -> dict:
    """Load data/chaos_bags.json (cached)."""
    global _BAG_DATA
    if _BAG_DATA is None:
        path = PROJECT_ROOT / "data" / "chaos_bags.json"
        _BAG_DATA = json.loads(path.read_text(encoding="utf-8"))
    return _BAG_DATA


def build_bag_tokens(
    campaign: str = "core", difficulty: str = "standard"
) -> list[ChaosTokenType]:
    """Official chaos bag composition for a campaign/difficulty.

    Falls back to the campaign default, then Standard difficulty, then the
    hardcoded STANDARD_BAG.
    """
    data = load_chaos_bag_data()
    campaigns = data.get("campaigns", {})
    cfg = campaigns.get(campaign) or campaigns.get(data.get("default_campaign", "core")) or {}
    difficulties = cfg.get("difficulties", {})
    diff_cfg = difficulties.get(difficulty) or difficulties.get("standard") or {}
    tokens: list[ChaosTokenType] = []
    for value, count in (diff_cfg.get("tokens") or {}).items():
        tokens.extend([ChaosTokenType(value)] * int(count))
    return tokens or list(STANDARD_BAG)


def bag_summary(campaign: str = "core", difficulty: str = "standard") -> dict:
    """UI-facing summary: token counts + difficulty labels."""
    tokens = build_bag_tokens(campaign, difficulty)
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t.value] = counts.get(t.value, 0) + 1
    data = load_chaos_bag_data()
    return {
        "campaign": campaign,
        "difficulty": difficulty,
        "difficulty_label": (data.get("difficulty_labels") or {}).get(difficulty, difficulty),
        "tokens": counts,
        "total": len(tokens),
    }


@dataclass
class ChaosBag:
    tokens: list[ChaosTokenType] = field(default_factory=lambda: list(STANDARD_BAG))
    sealed: list[ChaosTokenType] = field(default_factory=list)
    _rng: random.Random = field(default_factory=random.Random, repr=False)

    def seed(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def draw(self) -> ChaosTokenType:
        if not self.tokens:
            raise ValueError("Chaos bag is empty")
        idx = self._rng.randint(0, len(self.tokens) - 1)
        return self.tokens[idx]

    def remove(self, token: ChaosTokenType) -> bool:
        try:
            self.tokens.remove(token)
            return True
        except ValueError:
            return False

    def return_token(self, token: ChaosTokenType) -> None:
        self.tokens.append(token)

    def seal_token(self, token: ChaosTokenType) -> bool:
        if self.remove(token):
            self.sealed.append(token)
            return True
        return False

    def release_token(self, token: ChaosTokenType) -> bool:
        try:
            self.sealed.remove(token)
            self.tokens.append(token)
            return True
        except ValueError:
            return False

    def add_token(self, token: ChaosTokenType) -> None:
        self.tokens.append(token)
