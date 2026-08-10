"""Lockpicks (Level 1) — Rogue Asset, Hand slot.
使用(3补给)。若撬锁工具没有补给，弃置它。
[行动]消耗撬锁工具：调查。本次调查将你的敏捷值加到你的技能值上。
若你未成功至少2点，从撬锁工具上移除1补给。

简化说明：
- activate() 消耗本卡并武装；随后由会话层发起调查行动
  （武装后下一次调查生效，若先做了其他检定则武装在 SKILL_TEST_ENDS 时清除）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class Lockpicks(CardImplementation):
    card_id = "lockpicks_lv1"
    activations = [{"id": "investigate", "label": "消耗：调查（敏捷加到技能值）", "method": "activate"}]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_agility(self, ctx):
        """调查：将敏捷值加到技能值上。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(inv.get_skill(Skill.AGILITY), "lockpicks_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def remove_supply_on_low_margin(self, ctx):
        """成功但未超出难度至少2点：移除1补给。"""
        if not self._armed:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            self._remove_supply(ctx)

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def remove_supply_on_fail(self, ctx):
        """检定失败：移除1补给。"""
        if not self._armed:
            return
        self._remove_supply(ctx)

    def _remove_supply(self, ctx) -> None:
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inst.uses["supplies"] = inst.uses.get("supplies", 0) - 1
        ctx.extra["lockpicks_supply_removed"] = True
        if inst.uses["supplies"] <= 0:
            self._discard(ctx)

    def _discard(self, ctx) -> None:
        """补给耗尽：弃置撬锁工具。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("lockpicks_lv1")
        ctx.extra["lockpicks_discarded"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
