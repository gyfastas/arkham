"""Enchanted Blade (Level 3) — Guardian Asset, Hand + Arcane slots. (05192)
使用(3充能)。[行动]：攻击。本次攻击你获得+2战斗。如果成功，你可以花费1充能
强化刀刃，本次攻击造成+1伤害。如果强化后的本次攻击击败了一名敌人，
抽1张牌并治愈1点恐惧。

简化说明：
- +2战斗为武器被动（经 weapon_instance_id 识别）。
- "可以花费1充能强化"简化为成功时自动花费（有充能即花）。
- 强化的攻击击败敌人：FIGHT_ACTION_INITIATED 记录目标，ENEMY_DEFEATED 时
  若目标匹配且本次攻击已强化则抽1牌+治愈1恐惧。
- 数据 uses 键兼容 "charges"/"chargess"（抓取复数化瑕疵）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


def _charges_key(inst) -> str:
    if "charges" in inst.uses:
        return "charges"
    return "chargess" if "chargess" in inst.uses else "charges"


class EnchantedBlade(CardImplementation):
    card_id = "enchanted_blade_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._target = None
        self._empowered = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def record_target(self, ctx):
        if ctx.source == self.instance_id:
            self._target = ctx.enemy_id
            self._empowered = False

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """以本刃攻击：+2 战斗。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        ctx.modify_amount(2, "enchanted_blade_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def empower(self, ctx):
        """成功时：自动花费1充能强化，+1伤害。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = _charges_key(inst)
        if inst.uses.get(key, 0) <= 0:
            return
        inst.uses[key] -= 1
        self._empowered = True
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
        ctx.extra["enchanted_blade_empowered"] = True
        ctx.game_state.log_effect("🗡️ 附魔剑：花费1充能强化，+1伤害")

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def reward_on_defeat(self, ctx):
        """强化的攻击击败敌人：抽1张牌并治愈1点恐惧。"""
        if not self._empowered or ctx.target != self._target:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        if inv.horror > 0:
            inv.horror -= 1
        ctx.extra["enchanted_blade_reward"] = True
        ctx.game_state.log_effect("🗡️ 附魔剑：强化的攻击击败敌人，抽1牌并治愈1恐惧")
        self._empowered = False

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.source == self.instance_id:
            self._target = None
            self._empowered = False
