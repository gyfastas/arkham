"""Dark Ritual (Level 0) — Rogue Asset, Arcane slot. (07026)
封印（最多5[诅咒]）。
强制 - 当神话阶段结束时：你必须花费1资源或丢弃黑暗仪式。

简化说明：
- 入场时自动封印袋中所有可用[诅咒]（至多5个；官方为玩家选择数量，
  简化为全部封印——防守性用法）；离场时归还袋中（chthonian_stone 同模式）。
- 混沌袋经 bind_chaos_bag 注入（registry.activate_card 已接线）。
- 神话阶段结束的强制效果自动结算：有资源即花1资源，否则丢弃本卡
  （官方为二选一，简化为优先付资源）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_MAX_SEAL = 5


class DarkRitual(CardImplementation):
    card_id = "dark_ritual_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None
        self._sealed: list[ChaosTokenType] = []

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_curses_on_enter(self, ctx):
        """入场：封印至多5个[诅咒]（自动全封）。"""
        if ctx.target != self.instance_id or self._chaos_bag is None:
            return
        for _ in range(_MAX_SEAL):
            if not self._chaos_bag.seal_token(ChaosTokenType.CURSE):
                break
            self._sealed.append(ChaosTokenType.CURSE)
        if self._sealed:
            ctx.game_state.log_effect(
                f"🕯️ 黑暗仪式：封印{len(self._sealed)}个[诅咒]")

    def _release_sealed(self) -> None:
        if self._chaos_bag is not None:
            for token in self._sealed:
                self._chaos_bag.release_token(token)
        self._sealed = []

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        if ctx.target != self.instance_id:
            return
        self._release_sealed()

    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.FORCED)
    def pay_or_discard(self, ctx):
        """强制 - 神话阶段结束：花费1资源，否则丢弃本卡。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.resources >= 1:
            inv.resources -= 1
            ctx.game_state.log_effect("🕯️ 黑暗仪式：神话阶段结束，花费1资源维持")
            return
        # 丢弃本卡（镜像引擎弃置流程；先释放封印标记）
        self._release_sealed()
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(inst.card_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inst.owner_id)
        if slot_mgr is not None:
            slot_mgr.vacate(self.instance_id)
        ctx.game_state.log_effect("🕯️ 黑暗仪式：无资源可付，强制丢弃")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inv.investigator_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))
            self._bus.unregister_card(self.instance_id)
