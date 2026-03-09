"""Chaos bag implementation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.models.enums import ChaosTokenType


# Standard chaos bag configurations by difficulty
STANDARD_BAG = [
    ChaosTokenType.PLUS_1,
    ChaosTokenType.ZERO, ChaosTokenType.ZERO,
    ChaosTokenType.MINUS_1, ChaosTokenType.MINUS_1, ChaosTokenType.MINUS_1,
    ChaosTokenType.MINUS_2, ChaosTokenType.MINUS_2,
    ChaosTokenType.MINUS_3,
    ChaosTokenType.MINUS_4,
    ChaosTokenType.SKULL, ChaosTokenType.SKULL,
    ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET,
    ChaosTokenType.AUTO_FAIL,
    ChaosTokenType.ELDER_SIGN,
]


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
