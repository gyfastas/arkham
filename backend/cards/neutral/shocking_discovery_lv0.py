"""Shocking Discovery (Level 0) — Neutral Treachery, Weakness. (06009)
显现 - 将惊人发现洗回你的牌组。（若不能，改为丢弃它并抽取遭遇牌堆顶牌。）
强制 - 当你检索你的牌组且本卡在被检索的卡牌之中时：丢弃它。取消该次检索
及其所有效果。混洗被检索的牌组。抽取遭遇牌堆顶牌。

简化说明：
- "若不能洗回"的兜底分支（如设置阶段等无牌组可洗的情形）未接线——正常
  抽到牌组总是可以洗入；会话层若遇该情形可调用 resolve_cannot_shuffle()。
- 检索强制效果：引擎无牌组检索通道（检索均由各卡 handler 内联完成），
  on_searched() 供会话层/检索类卡牌在检索到本卡时调用；检索取消由调用方
  负责中止（本方法返回 True 表示触发）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ShockingDiscovery(CardImplementation):
    card_id = "shocking_discovery_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "shocking_discovery_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "shocking_discovery_lv0" in inv.hand:
            inv.hand.remove("shocking_discovery_lv0")
        # 洗回牌组
        inv.deck.append("shocking_discovery_lv0")
        random.shuffle(inv.deck)
        ctx.extra["shocking_discovery_shuffled"] = True

    def on_searched(self, game_state, investigator_id) -> bool:
        """检索牌组时检索到本卡：丢弃之，混洗牌组，抽遭遇牌堆顶牌。

        返回 True 表示触发（调用方应取消检索及其效果）。
        """
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if "shocking_discovery_lv0" in inv.deck:
            inv.deck.remove("shocking_discovery_lv0")
        inv.discard.append("shocking_discovery_lv0")
        random.shuffle(inv.deck)
        self._draw_encounter(game_state, investigator_id)
        return True

    def resolve_cannot_shuffle(self, game_state, investigator_id) -> None:
        """显现兜底：不能洗回时丢弃并抽遭遇牌堆顶牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return
        if "shocking_discovery_lv0" in inv.hand:
            inv.hand.remove("shocking_discovery_lv0")
        inv.discard.append("shocking_discovery_lv0")
        self._draw_encounter(game_state, investigator_id)

    def _draw_encounter(self, game_state, investigator_id) -> None:
        if not game_state.scenario.encounter_deck:
            return
        card_id = game_state.scenario.encounter_deck.pop(0)
        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.ENCOUNTER_CARD_DRAWN,
                investigator_id=investigator_id,
                extra={"card_id": card_id},
            ))

    def register(self, bus, instance_id: str) -> None:
        self._bus = bus
        super().register(bus, instance_id)
