"""Occult Evidence (Level 0) — Neutral Event. Mandy Thompson 专属.
将神秘学证据洗入你的牌组。
[reaction] 当你检索你的牌库且神秘学证据在被检索的卡牌中时，展示之：
抽取它，并在你所在地点发现1条线索。（每次检索至多触发一个
[[Research]]能力。）

简化说明：
- 打出即洗入牌组。引擎 _play_event 在 CARD_PLAYED 后无条件置入弃牌堆，
  弃牌堆残留为已知偏差（牌库中的复制为权威状态）。
- "当你检索牌库时"无引擎事件（引擎缺口），实现为公开方法
  on_deck_searched()，由会话层在检索时调用；可传 searched_card_ids
  （被检索的卡牌列表），默认视为检索整个牌库。
- 线索发现复刻 actions._investigate 的 CLUE_DISCOVERED 流程。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, TimingPriority


class OccultEvidence(CardImplementation):
    card_id = "occult_evidence_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def shuffle_into_deck(self, ctx):
        if ctx.extra.get("card_id") != "occult_evidence_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inv.deck.append("occult_evidence_lv0")
        random.shuffle(inv.deck)
        ctx.game_state.log_effect("🔎 神秘学证据：洗入你的牌组")

    def on_deck_searched(self, game_state, investigator_id,
                         searched_card_ids: list[str] | None = None) -> bool:
        """[reaction] 检索牌库时若本卡在被检索卡牌中：抽取并发现1线索。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        searched = searched_card_ids if searched_card_ids is not None else list(inv.deck)
        if "occult_evidence_lv0" not in searched:
            return False
        if "occult_evidence_lv0" not in inv.deck:
            return False
        inv.deck.remove("occult_evidence_lv0")
        inv.hand.append("occult_evidence_lv0")

        location = game_state.get_location(inv.location_id)
        if location is not None and location.clues > 0:
            location.clues -= 1
            inv.clues += 1
            if self._bus is not None:
                self._bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=investigator_id,
                    location_id=inv.location_id,
                    amount=1,
                ))
        game_state.log_effect("🔎 神秘学证据：检索中展示，抽取并发现1条线索")
        return True
