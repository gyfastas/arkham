"""刀子（Knife，Level 0）— Neutral Asset, Hand slot.
[行动]：攻击。本次攻击+1战斗。
[行动]弃置刀子：攻击。本次攻击+2战斗、+1伤害。

简化说明：
- 弃刀攻击实现为 activate_discard_attack() 武装 + 以刀子发起的下一次
  战斗（FIGHT 行动，正常消耗1行动）获得+2战斗/+1伤害，并在攻击发起时
  弃刀。武装本身不耗行动，整体行动经济与卡面一致（共1行动）；UI 上需要
  先点启动能力再执行战斗，特此注明。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Knife(CardImplementation):
    card_id = "knife_lv0"
    activations = [{
        "id": "discard_attack",
        "label": "弃置刀子：攻击（+2战斗、+1伤害）",
        "method": "activate_discard_attack",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._discard_armed = False   # 弃刀攻击已武装
        self._discard_attack = False  # 本次攻击为弃刀攻击

    def activate_discard_attack(self, game_state, investigator_id: str) -> bool:
        """[action] 弃置刀子：攻击。本次攻击+2战斗、+1伤害。

        武装弃刀攻击；随后以刀子发起的战斗在攻击发起时弃刀并获得加值。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._discard_armed = True
        return True

    @on_event(
        GameEvent.FIGHT_ACTION_INITIATED,
        priority=TimingPriority.WHEN,
    )
    def discard_on_attack(self, ctx):
        """弃刀攻击发起时弃置刀子（作为攻击费用，无论命中与否）。"""
        self._discard_attack = False
        if ctx.source != self.instance_id or not self._discard_armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        manager = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if manager:
            manager.vacate(self.instance_id)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        self._discard_armed = False
        self._discard_attack = True

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat when fighting with this weapon (+2 for the discard attack)."""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = 2 if self._discard_attack else 1
        ctx.modify_amount(bonus, "knife_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage for the discard attack."""
        if ctx.source != self.instance_id or not self._discard_attack:
            return
        ctx.modify_amount(1, "knife_extra_damage")

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_flags(self, ctx):
        # 武装状态保留到下一次以刀子发起的攻击；仅清理本次攻击标记
        self._discard_attack = False
