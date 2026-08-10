"""Enchanted Blade (Level 0) — Mystic Asset, Hand+Arcane slots. (05118)
使用(3充能)。[action]：攻击。本次攻击+1[combat]。作为发动此能力的额外费用，
你可以花费1充能来为剑附魔。如果你这么做，本次攻击再+1[combat]并造成+1伤害。

简化说明：
- 基础+1战斗：以本卡为武器（weapon_instance_id 传本卡实例）的攻击自动生效
  （同 machete 惯例，无需武装）。
- 附魔为可选额外费用：会话层在发起攻击前调用 empower()（或在 FIGHT 时由
  UI 选择）；已付充能武装至本次检定结束，未攻击不退还（官方：费用在发动
  攻击时支付）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class EnchantedBlade(CardImplementation):
    card_id = "enchanted_blade_lv0"
    base_combat_bonus = 1       # lv3 覆盖：+2
    max_empower_charges = 1     # lv3 覆盖：至多2充能

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._empowered = 0  # 本次攻击已附魔的充能数

    def empower(self, game_state, investigator_id: str, charges: int = 1) -> bool:
        """发动攻击前的额外费用：花费至多N充能为剑附魔（每充能+1战斗+1伤害）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        charges = int(charges)
        if charges <= 0 or charges > self.max_empower_charges:
            return False
        available = inst.uses.get("charges", 0)
        if available < charges:
            return False
        inst.uses["charges"] = available - charges
        self._empowered = charges
        return True

    def _is_this_weapon(self, ctx) -> bool:
        return ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_weapon(ctx):
            return
        ctx.modify_amount(
            self.base_combat_bonus + self._empowered,
            f"{self.card_id}_combat_bonus",
        )

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """附魔每充能：+1伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if not self._is_this_weapon(ctx) or self._empowered <= 0:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + self._empowered

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._empowered = 0
