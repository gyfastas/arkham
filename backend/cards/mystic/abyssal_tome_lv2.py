"""Abyssal Tome (Level 2) — Mystic Asset, Hand slot. (07159)
[action]消耗深渊典籍：攻击。这次攻击你可以不使用[combat]，改为使用[intellect]
或[willpower]。在你发动这次攻击时，你可以在深渊典籍上放置1个毁灭标记（最多3个）。
深渊典籍每有一个毁灭标记，这次攻击你+1技能值并造成+1伤害。

简化说明：
- activate() 消耗本卡并武装；place_doom=True 时放置1毁灭（上限3，满则不放）。
  毁灭是否放置为玩家可选，默认不放（毁灭有推进议程风险）。
- 随后由会话层发起战斗行动（weapon_instance_id 传本卡实例），检定时以所选
  技能代替战斗，并按本卡上的毁灭数追加技能值；成功时按毁灭数追加伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

MAX_DOOM = 3


class AbyssalTome(CardImplementation):
    card_id = "abyssal_tome_lv2"
    activations = [{
        "id": "fight",
        "label": "消耗：用意志/智力攻击，每毁灭+1技能值+1伤害",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._skill = Skill.WILLPOWER

    def activate(self, game_state, investigator_id: str,
                 skill: Skill = Skill.WILLPOWER, place_doom: bool = False) -> bool:
        """消耗深渊典籍：武装一次攻击；可选放置1毁灭（最多3）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if skill not in (Skill.WILLPOWER, Skill.INTELLECT):
            return False
        inst.exhausted = True
        if place_doom and inst.doom < MAX_DOOM:
            inst.doom += 1
        self._armed = True
        self._skill = skill
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    def _doom(self, ctx) -> int:
        inst = ctx.game_state.get_card_instance(self.instance_id)
        return inst.doom if inst is not None else 0

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_skill(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        chosen = inv.get_skill(self._skill)
        ctx.modify_amount(
            chosen - base_val + self._doom(ctx),
            "abyssal_tome_substitute",
        )

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """每个毁灭标记：+1伤害。"""
        if not self._is_this_attack(ctx):
            return
        doom = self._doom(ctx)
        if doom > 0:
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + doom

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._skill = Skill.WILLPOWER
