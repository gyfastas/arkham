"""Ríastrad (Level 1) — Rogue Event. (07193)
攻击。在你发动这次攻击时，加入最多3个[curse]标记到混乱袋。每以此方式
加入1个[curse]标记到混乱袋，你这次攻击+1[combat]并造成+1伤害。

简化说明：
- "最多3个"自动选择加入3个（可用 ctx.extra["curse_count"] 指定0-3）；
  诅咒标记对后续检定不利，官方为玩家权衡选择。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
- 打出后由会话层发起战斗行动；+战斗/+伤害仅作用于紧随的第一次战斗检定，
  SKILL_TEST_ENDS 清除武装。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority


class Riastrad(CardImplementation):
    card_id = "ríastrad_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._curses = 0

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def add_curses(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        count = ctx.extra.get("curse_count", 3)
        count = max(0, min(3, int(count)))
        bag = getattr(self, "_chaos_bag", None)
        if bag is not None:
            for _ in range(count):
                bag.add_token(ChaosTokenType.CURSE)
        self._curses = count
        ctx.extra["riastrad_curses"] = count
        if count:
            ctx.game_state.log_effect(
                f"🌀 狂化：向混沌袋加入{count}个诅咒标记，本次攻击+{count}战斗/+{count}伤害")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if not self._curses or ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(self._curses, "riastrad_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if not self._curses or ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + self._curses

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._curses = 0
