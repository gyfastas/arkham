"""Colt Vest Pocket (Level 0) — Rogue Asset, Hand slot. (04268)
使用(5子弹)。
[行动]花费1子弹：攻击。这次攻击中你+1战斗。这次攻击造成+1伤害。
强制 - 当本轮结束时：丢弃柯尔特袖珍手枪。

简化说明：
- 子弹在发起攻击时（FIGHT_ACTION_INITIATED）扣除，无子弹时取消攻击
  （lupara 同模式）。
- +1伤害经 ctx.extra["bonus_damage"] 通道汇入战斗结算。
- 回合结束的自弃为强制效果，自动执行：从场上移除并置入拥有者弃牌堆，
  释放槽位并经事件总线发出 CARD_LEAVES_PLAY（镜像引擎弃置流程）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ColtVestPocket(CardImplementation):
    card_id = "colt_vest_pocket_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attack_paid = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """花费1子弹：攻击。无子弹时攻击被取消（不花费行动）。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            self._attack_paid = False
            ctx.cancel()
            ctx.game_state.log_effect("🔫 柯尔特袖珍手枪：没有子弹，攻击取消")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击+1战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(1, "colt_vest_pocket_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """本次攻击造成+1伤害（经 bonus_damage 通道结算）。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_state(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.FORCED)
    def discard_at_round_end(self, ctx):
        """强制 - 当本轮结束时：丢弃本卡。"""
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        inv = ctx.game_state.get_investigator(card.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(card.card_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(card.owner_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        ctx.game_state.log_effect("🔫 柯尔特袖珍手枪：本轮结束，强制丢弃")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=card.owner_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
            self._bus.unregister_card(self.instance_id)
