"""Talisman of Protection (Level 0) — Mystic Asset, Arcane slot. (08116)
快速。只能在你的回合中打出。打出时置于你所在地点任一调查员控制之下。
[reaction] 在你被分配足以击败你的伤害和/或恐惧时，丢弃本卡：取消其中
至多2点伤害和/或恐惧。

简化说明：
- "足以击败你"按单一分配事件判定：DAMAGE_ASSIGNED 时
  伤害+已有伤害≥生命，或 HORROR_ASSIGNED 时恐惧+已有恐惧≥理智。
  伤害与恐惧合并判败（如 2伤+2恐 各自不足但合并致命）的情形无法识别
  （引擎对伤害/恐惧分别发射事件且无待结算视图，缺口）。
- 取消上限2点在首次满足条件的事件中一次用完（伤害/恐惧混合分配时无法
  拆分，同上缺口）；随后本卡自动丢弃（自动触发，官方为玩家选择时机）。
- "置于任一调查员控制之下"由打出流程决定 controller；本实现只对
  controller 本人的分配生效。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TalismanOfProtection(CardImplementation):
    card_id = "talisman_of_protection_lv0"
    cancel_amount = 2

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _controlled_by(self, game_state, investigator_id: str) -> bool:
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.controller_id != investigator_id:
            return False
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_damage(self, ctx):
        if not self._controlled_by(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv.damage + (ctx.amount or 0) < inv.health:
            return  # 不足以击败
        cancelled = min(self.cancel_amount, ctx.amount or 0)
        if cancelled > 0:
            ctx.modify_amount(-cancelled, "talisman_of_protection")
        ctx.extra["talisman_of_protection_cancelled"] = cancelled
        ctx.game_state.log_effect(f"🧿 护身法宝：丢弃，取消{cancelled}点伤害")
        self._discard_self(ctx.game_state, inv)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_horror(self, ctx):
        if not self._controlled_by(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv.horror + (ctx.amount or 0) < inv.sanity:
            return
        cancelled = min(self.cancel_amount, ctx.amount or 0)
        if cancelled > 0:
            ctx.modify_amount(-cancelled, "talisman_of_protection")
        ctx.extra["talisman_of_protection_cancelled"] = cancelled
        ctx.game_state.log_effect(f"🧿 护身法宝：丢弃，取消{cancelled}点恐惧")
        self._discard_self(ctx.game_state, inv)

    def _discard_self(self, game_state, inv) -> None:
        from backend.engine.event_bus import EventContext

        inst = game_state.cards_in_play.pop(self.instance_id, None)
        if inst is None:
            return
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        inv.discard.append(inst.card_id)
        mgr = getattr(game_state, "slot_managers", {}).get(inv.investigator_id)
        if mgr is not None:
            mgr.vacate(self.instance_id)
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": inst.card_id},
            ))
