"""Dragon Pole (Level 0) — Mystic Asset, Hand x2 slots. (08060)
你拥有1个额外的法术槽位。
[action]：攻击。你每有一个法术槽位被占用，本次攻击+1[combat]。
如果你有至少2个法术槽位被占用，本次攻击造成+1伤害。

简化说明：
- 额外法术槽位：入场时经 slot_managers 增加1个 arcane 奖励槽位，离场移除
  （同 Charisma 等 bonus_slots 惯例）。
- 战斗加值按攻击者已占用的法术槽位数计算（slot manager 优先；无 slot
  manager 时按 play_area 中占用 arcane 槽的支援数兜底）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, SlotType, TimingPriority


class DragonPole(CardImplementation):
    card_id = "dragon_pole_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """入场：+1法术槽位。"""
        if ctx.target != self.instance_id:
            return
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            ctx.investigator_id)
        if slot_mgr is not None:
            slot_mgr.add_bonus(SlotType.ARCANE, 1)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        """离场：移除额外法术槽位。"""
        if ctx.target != self.instance_id:
            return
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            ctx.investigator_id)
        if slot_mgr is not None:
            slot_mgr.remove_bonus(SlotType.ARCANE, 1)

    def _filled_arcane_slots(self, ctx) -> int:
        """攻击者已被占用的法术槽位数。"""
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            ctx.investigator_id)
        if slot_mgr is not None:
            return len(slot_mgr.slots.get(SlotType.ARCANE, []))
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return 0
        count = 0
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            if ci is not None and SlotType.ARCANE in ci.slot_used:
                count += 1
        return count

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """每个被占用的法术槽位：+1战斗。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        filled = self._filled_arcane_slots(ctx)
        if filled > 0:
            ctx.modify_amount(filled, "dragon_pole_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """至少2个法术槽位被占用：+1伤害。"""
        if ctx.source != self.instance_id:
            return
        if self._filled_arcane_slots(ctx) >= 2:
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
