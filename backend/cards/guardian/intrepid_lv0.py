"""Intrepid (Level 0) — Guardian Skill. (04192)
如果本次技能检定成功，将无畏放置入场（你的游戏区），视为支援卡，卡牌文本为：
"你获得+1[智力]、+1[战斗]和+1[敏捷]。
强制 - 在本回合结束时：丢弃无畏。"

简化说明：
- 投入成功后本卡从手牌放置入场（不移入弃牌堆——引擎 ST.8 只弃置仍在
  手牌的投入卡，先入场的不会重复入弃牌堆）。
- 入场后的持续效果需要一个挂在场上实例上的实现：提交时的临时实现会在
  ST.8 后被注册表注销，因此本卡在 SKILL_TEST_ENDS 时为场上实例手动
  重新注册一个新实现（自包含，无需会话层接线）。
- 回合结束时的丢弃在 ROUND_ENDS 处理（含离场事件与弃牌堆）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance

_BONUS_SKILLS = (Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY)


class Intrepid(CardImplementation):
    card_id = "intrepid_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._entered_instance: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def enter_play_on_success(self, ctx):
        """检定成功：从手牌放置入场（你的游戏区）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        inv.hand.remove(self.card_id)  # 入场而非弃置（ST.8 不再处理它）
        instance_id = ctx.game_state.next_instance_id()
        ctx.game_state.cards_in_play[instance_id] = CardInstance(
            instance_id=instance_id,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
        )
        inv.play_area.append(instance_id)
        self._entered_instance = instance_id
        ctx.extra["intrepid_entered_play"] = instance_id
        ctx.game_state.log_effect(
            "🦁 无畏：检定成功，放置入场（+1智力/+1战斗/+1敏捷，回合结束丢弃）")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def reregister_in_play(self, ctx):
        """为场上实例重新注册实现（提交用临时实现随后被注册表注销）。"""
        if self._entered_instance is None or self._bus is None:
            return
        instance_id = self._entered_instance
        self._entered_instance = None
        if ctx.game_state.get_card_instance(instance_id) is None:
            return
        Intrepid(instance_id).register(self._bus, instance_id)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """在场时：+1智力、+1战斗、+1敏捷。"""
        if ctx.skill_type not in _BONUS_SKILLS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "intrepid_bonus")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def discard_at_round_end(self, ctx):
        """强制 - 回合结束时：丢弃无畏。"""
        inv = None
        for candidate in ctx.game_state.investigators.values():
            if self.instance_id in candidate.play_area:
                inv = candidate
                break
        if inv is None:
            return
        inv.play_area.remove(self.instance_id)
        inv.discard.append(self.card_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
            self.unregister(self._bus)
        ctx.game_state.log_effect("🦁 无畏：回合结束，丢弃")
