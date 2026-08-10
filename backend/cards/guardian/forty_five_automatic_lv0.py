""".45 Automatic (Level 0) — Guardian Asset, Hand slot.
使用(4弹药)。[行动]花费1弹药：攻击。本次攻击你获得+1战斗，造成+1伤害。

简化说明：
- 弹药在命中时扣除（引擎没有发起攻击时的扣费通道，失手不扣）。
- 弹药为0时攻击加成不生效（等同徒手攻击）；引擎层无法阻止发起攻击本身，
  完整的"无弹药不能攻击"需要引擎/会话层支持，见 docstring 说明。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyFiveAutomatic(CardImplementation):
    card_id = "45_automatic_lv0"

    def _has_ammo(self, game_state) -> bool:
        card = game_state.get_card_instance(self.instance_id)
        return card is not None and card.uses.get("ammo", 0) > 0

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def combat_bonus(self, ctx):
        """+1 Combat when fighting with this weapon (requires ammo)."""
        if ctx.source != self.instance_id:
            return
        if not self._has_ammo(ctx.game_state):
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "45_auto_combat_bonus")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def extra_damage(self, ctx):
        """+1 damage when attacking with this weapon; spend 1 ammo on hit."""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card and card.uses.get("ammo", 0) > 0:
            card.uses["ammo"] -= 1
            ctx.modify_amount(1, "45_auto_extra_damage")
