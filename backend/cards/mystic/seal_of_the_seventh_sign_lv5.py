"""Seal of the Seventh Sign (Level 5) — Mystic Asset, Arcane slot. (04311)
封印([auto_fail])。使用(7充能)。如果本卡没有充能，或者离场，将其从游戏中移除。
强制 - 在任何技能检定中揭示[skull]、[cultist]、[tablet]或[elder_thing]标记后：
移除本卡1充能。

简化说明：
- 封印经 bind_chaos_bag 注入的混沌袋实现（registry.activate_card 生产接线）：
  入场时将袋中 [auto_fail] 封印到本卡。ChaosBag.sealed 为全局列表，卡面级
  归属由本实现的 _sealed 维护；离场时封印标记归还袋中。
- "移出游戏"：引擎无移除区，登记在 scenario.vars["removed_from_game"]
  （同 seal_of_the_elder_sign 惯例），并从弃牌堆等常规去处剔除。
- 数据 JSON 中 uses 键为 "chargess"（上游笔误），经 seeker._uses 兼容读取。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_spend
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class SealOfTheSeventhSign(CardImplementation):
    card_id = "seal_of_the_seventh_sign_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._sealed: list[ChaosTokenType] = []
        self._removed = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    # ------------------------------------------------------------------
    # 封印 / 离场
    # ------------------------------------------------------------------
    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_auto_fail(self, ctx):
        """入场：将袋中 [auto_fail] 封印到本卡。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is not None and self._bag.seal_token(ChaosTokenType.AUTO_FAIL):
            self._sealed.append(ChaosTokenType.AUTO_FAIL)
            ctx.game_state.log_effect("✡ 第七印记的封印：封印 [auto_fail] 标记")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def on_leaves_play(self, ctx):
        """离场：归还封印标记，并将本卡移出游戏。"""
        if ctx.target != self.instance_id or self._removed:
            return
        self._release_sealed()
        self._register_removed_from_game(ctx.game_state)

    # ------------------------------------------------------------------
    # 强制：符号标记移除充能
    # ------------------------------------------------------------------
    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.FORCED)
    def remove_charge_on_symbol(self, ctx):
        """任何检定揭示 skull/cultist/tablet/elder_thing 后：移除1充能。"""
        if self._removed or ctx.chaos_token not in _SYMBOL_TOKENS:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if not uses_spend(inst, "charges"):
            return
        ctx.game_state.log_effect("✡ 第七印记的封印：符号标记揭示，移除1充能")
        if uses_count(inst, "charges") <= 0:
            ctx.game_state.log_effect("✡ 第七印记的封印：充能耗尽，移出游戏")
            self._remove_from_game(ctx.game_state)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _release_sealed(self) -> None:
        if self._bag is not None:
            for token in self._sealed:
                self._bag.release_token(token)
        self._sealed = []

    def _register_removed_from_game(self, game_state) -> None:
        self._removed = True
        removed = game_state.scenario.vars.setdefault("removed_from_game", [])
        if self.card_id not in removed:
            removed.append(self.card_id)
        # 从弃牌堆/手牌剔除（离场流程可能已将其放入弃牌堆）
        for inv in game_state.investigators.values():
            for zone in (inv.discard, inv.hand):
                while self.card_id in zone:
                    zone.remove(self.card_id)

    def _remove_from_game(self, game_state) -> None:
        """充能耗尽：归还封印、离场并移出游戏。"""
        from backend.engine.event_bus import EventContext

        inst = game_state.cards_in_play.pop(self.instance_id, None)
        if inst is None:
            self._register_removed_from_game(game_state)
            return
        inv = game_state.get_investigator(inst.owner_id)
        if inv is not None and self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        mgr = getattr(game_state, "slot_managers", {}).get(inst.owner_id)
        if mgr is not None:
            mgr.vacate(self.instance_id)
        self._release_sealed()
        self._register_removed_from_game(game_state)
        bus = getattr(self, "_bus", None)
        if bus is not None:
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=inst.owner_id,
                target=self.instance_id,
                extra={"card_id": self.card_id},
            ))

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
