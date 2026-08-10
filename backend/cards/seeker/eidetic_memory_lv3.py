"""Eidetic Memory (Level 3) — Seeker Event.
将本卡作为任意调查员弃牌堆中1张[[Insight]]事件的精确复制打出
（含其资源费用）。将该事件移出游戏。本卡以移出游戏代替弃置。

简化说明：
- 复制目标默认为所有弃牌堆中第一张（费用可承担的）Insight事件，
  可用 ctx.extra["copy_card_id"] 指定；
- 复制效果通过临时注册目标卡实现并在事件总线上重放 CARD_PLAYED 完成
  （卡实现拿不到 Game.card_registry，故现场构建一个注册表来查找实现类）。
  依赖"在手牌中"判定的事件（如 Lucky!）无法以此方式生效；
- "移出游戏代替弃置"：引擎在 CARD_PLAYED 结算后才把事件放入弃牌堆，
  无拦截钩子，故延迟到 ROUND_ENDS 从弃牌堆移出
  （移除区记录在 scenario.vars["removed_from_game"]，与 Abandoned and Alone 一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class EideticMemory(CardImplementation):
    card_id = "eidetic_memory_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._remove_pending: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def copy_insight_event(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._remove_pending = ctx.investigator_id

        chosen = self._choose_copy_target(ctx, inv)
        if chosen is None:
            ctx.game_state.log_effect("🧠 过目不忘：弃牌堆中没有可复制的洞察事件")
            return
        owner_id, copy_id, cost = chosen
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is None:
            return

        inv.resources -= cost
        owner.discard.remove(copy_id)
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []).append(copy_id)
        ctx.extra["eidetic_memory_copied"] = copy_id
        ctx.game_state.log_effect(
            f"🧠 过目不忘：复制【{ctx.game_state.card_name(copy_id)}】"
            f"（支付{cost}资源），该事件移出游戏"
        )
        self._replay_copied_event(ctx, copy_id)

    def _choose_copy_target(self, ctx, inv):
        """选出 (owner_id, card_id, cost)；默认第一张费用可承担的洞察事件。"""
        candidates = []
        for owner_id, owner in ctx.game_state.investigators.items():
            for cid in owner.discard:
                cd = ctx.game_state.get_card_data(cid)
                if cd is None or cd.type != CardType.EVENT:
                    continue
                if "insight" not in [t.lower() for t in (cd.traits or [])]:
                    continue
                candidates.append((owner_id, cid, cd.cost or 0))
        wanted = ctx.extra.get("copy_card_id")
        if wanted is not None:
            for c in candidates:
                if c[1] == wanted and c[2] <= inv.resources:
                    return c
            return None
        for c in candidates:
            if c[2] <= inv.resources:
                return c
        return None

    def _replay_copied_event(self, ctx, copy_id: str) -> None:
        """临时注册被复制事件的实现并重放 CARD_PLAYED。"""
        bus = self._bus
        if bus is None:
            return
        from backend.cards.registry import CardRegistry
        registry = CardRegistry()
        registry.discover_cards()
        temp_id = ctx.game_state.next_instance_id()
        impl = registry.activate_card(copy_id, temp_id, bus)
        if impl is None:
            return
        try:
            from backend.engine.event_bus import EventContext
            sub_ctx = EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_PLAYED,
                investigator_id=ctx.investigator_id,
                source=temp_id,
                extra={**ctx.extra, "card_id": copy_id,
                       "copied_by": self.card_id},
            )
            bus.emit(sub_ctx)
        finally:
            registry.deactivate_card(temp_id, bus)

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def remove_from_game_instead(self, ctx):
        """本卡以移出游戏代替弃置（引擎在出牌结算后才放入弃牌堆，延迟清理）。"""
        if self._remove_pending is None:
            return
        inv = ctx.game_state.get_investigator(self._remove_pending)
        self._remove_pending = None
        if inv is not None and self.card_id in inv.discard:
            inv.discard.remove(self.card_id)
            ctx.game_state.scenario.vars.setdefault(
                "removed_from_game", []).append(self.card_id)
