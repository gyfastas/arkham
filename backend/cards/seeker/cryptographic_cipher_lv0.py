"""Cryptographic Cipher (Level 0) — Seeker Asset, Hand slot. (07021)
使用(3秘密)。
[快速]横置密码密码机并花费1秘密：调查。本次调查中你所在地点+1隐蔽值。
[行动]横置密码密码机并花费1秘密：调查。本次调查中你所在地点-2隐蔽值。

简化说明：
- 两个能力均为"武装一次调查"模式（与 flashlight 一致）：activate_*() 横置
  并花费秘密后，由会话层发起调查行动，隐蔽修正在 SKILL_TEST_BEGINS 施加；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_spend
from backend.models.enums import GameEvent, Skill, TimingPriority


class CryptographicCipher(CardImplementation):
    card_id = "cryptographic_cipher_lv0"
    activations = [
        {"id": "quick", "label": "[快速]横置+1秘密：调查，地点+1隐蔽",
         "method": "activate_quick"},
        {"id": "deep", "label": "[行动]横置+1秘密：调查，地点-2隐蔽",
         "method": "activate", "actions": 1},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._shroud_delta = 0

    def activate_quick(self, game_state, investigator_id: str) -> bool:
        """[快速]横置+1秘密：下一次调查地点+1隐蔽。"""
        return self._arm(game_state, investigator_id, +1)

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]横置+1秘密：下一次调查地点-2隐蔽。"""
        return self._arm(game_state, investigator_id, -2)

    def _arm(self, game_state, investigator_id: str, delta: int) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if not uses_spend(inst, "secrets"):
            return False
        inst.exhausted = True
        self._armed_by = investigator_id
        self._shroud_delta = delta
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def adjust_shroud(self, ctx):
        """本次调查：地点隐蔽值按武装方向修正。"""
        if self._armed_by != ctx.investigator_id:
            return
        if ctx.skill_type != Skill.INTELLECT or ctx.difficulty is None:
            return
        ctx.difficulty = max(0, ctx.difficulty + self._shroud_delta)
        ctx.extra["cryptographic_cipher_adjusted"] = self._shroud_delta

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
        self._shroud_delta = 0
