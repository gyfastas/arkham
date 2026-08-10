"""Enchanted Bow (Level 2) — Mystic Asset, Hand x2 + Arcane slots. (08118)
使用(3充能)。[action]消耗附魔弓：攻击。你本次攻击+1技能值，并且必须不使用
[combat]，改为使用[willpower]或[agility]。本次攻击造成+1伤害。作为发动本能力的
额外费用，你可以花费1充能使本次攻击以连接地点的一名非[[精英]]敌人为目标；
如果你这么做，本次攻击忽略冷漠和反击关键词。

简化说明：
- activate(skill=...) 消耗本卡并武装；随后由会话层发起战斗行动
  （weapon_instance_id 传本卡实例），检定时以所选技能代替战斗并+1技能值。
- 远程选项：activate(ranged=True) 时花费1充能，记录 ctx.extra 标记供会话层
  放宽目标合法性（连接地点非精英敌人）；忽略反击无法拦截引擎失败结算
  （actions._fight 直接按关键词反伤，无事件通道——引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class EnchantedBow(CardImplementation):
    card_id = "enchanted_bow_lv2"
    activations = [{
        "id": "fight",
        "label": "消耗：用意志/敏捷攻击，+1技能值+1伤害",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._skill = Skill.WILLPOWER
        self._ranged = False

    def activate(self, game_state, investigator_id: str,
                 skill: Skill = Skill.WILLPOWER, ranged: bool = False) -> bool:
        """消耗附魔弓：武装一次攻击。ranged=True 时额外花费1充能瞄准连接地点。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if skill not in (Skill.WILLPOWER, Skill.AGILITY):
            return False
        if ranged:
            if inst.uses.get("charges", 0) <= 0:
                return False
            inst.uses["charges"] -= 1
        inst.exhausted = True
        self._armed = True
        self._skill = skill
        self._ranged = ranged
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_skill(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        chosen = inv.get_skill(self._skill)
        # 所选技能代替战斗，并+1技能值
        ctx.modify_amount(chosen - base_val + 1, "enchanted_bow_substitute")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if not self._is_this_attack(ctx):
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
        if self._ranged:
            ctx.extra["enchanted_bow_ignore_aloof_retaliate"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._ranged = False
        self._skill = Skill.WILLPOWER
