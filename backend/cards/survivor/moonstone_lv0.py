"""Moonstone (Level 0) — Survivor Asset, Accessory slot. (06203)
You get +1 [willpower] and +1 [agility].
You cannot play or commit Moonstone from your hand.
[reaction] After you discard Moonstone from your hand: Play it
(paying its cost).

简化说明：
- "不能从手牌打出/投入"为打出限制，需会话层/UI 支持，本实现不强制
  （引擎缺口，见报告）。
- 引擎无 CARD_DISCARDED 发出点（引擎缺口）；"从手牌弃置后打出"实现为
  公开方法 discard_and_play()：弃置 + 支付费用 + 放置入场一步完成
  （复刻 _play_asset 流程；实现注册需会话层对新实例 activate，
  同 a_chance_encounter 缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance


class Moonstone(CardImplementation):
    card_id = "moonstone_lv0"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 供 CARD_ENTERS_PLAY 事件使用

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_bonus(self, ctx):
        """在场时 +1 意志、+1 敏捷。"""
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "moonstone_passive")

    def discard_and_play(self, game_state, investigator_id: str) -> bool:
        """[reaction] 你从手牌弃置月光石后：支付费用将其打出。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return False
        cd = game_state.get_card_data(self.card_id)
        cost = (cd.cost or 0) if cd else 0
        if inv.resources < cost:
            return False
        inv.resources -= cost
        inv.hand.remove(self.card_id)  # 弃置后被反应立即打出，不进弃牌堆

        # 放置入场（复刻 _play_asset）
        instance_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=self.card_id,
            owner_id=investigator_id,
            controller_id=investigator_id,
            slot_used=list(cd.slots or []) if cd else [],
        )
        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if slot_mgr and cd and cd.slots:
            slot_mgr.occupy(instance_id, cd.slots, cd.traits)
        game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)

        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=investigator_id,
                target=instance_id,
                extra={"card_id": self.card_id},
            ))
        game_state.log_effect(
            f"🌙 月光石：从手牌弃置后打出（支付{cost}资源）")
        return True
