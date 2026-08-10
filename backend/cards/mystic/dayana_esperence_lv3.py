"""Dayana Esperence (Level 3) — Mystic Asset, Ally slot. (05279)
使用(3秘密)。
[fast]：将一张非弱点[[法术]]事件卡从你的手牌叠加到黛雅娜·艾丝帕伦斯。
被叠加到其身上的事件卡限制1张。
可以打出被叠加的事件卡，如同其在你的手牌中。将其打出后，不放到你的
弃牌堆（其仍维持叠加）。作为打出被叠加事件卡的额外费用，消耗黛雅娜·
艾丝帕伦斯并花费1秘密。

简化说明：
- attach_event() 叠加手牌中的非弱点法术事件（限1张）。
- play_attached() 支付额外费用（消耗+1秘密），把事件放回手牌并返回
  card_id，由会话层按正常流程打出（资源费用照付）；打出后经
  CARD_PLAYED/ACTION_PERFORMED 追踪，从弃牌堆重新叠加回本卡。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card


class DayanaEsperence(CardImplementation):
    card_id = "dayana_esperence_lv3"
    activations = [
        {"id": "attach", "label": "[快速]叠加手牌中的法术事件（限1张）",
         "method": "attach_event"},
        {"id": "play", "label": "消耗+1秘密：打出叠加的事件",
         "method": "play_attached"},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: str | None = None
        self._awaiting_play: str | None = None  # play_attached 已付额外费用
        self._played_via_dayana: str | None = None  # 已打出待重新叠加

    @property
    def attached_event(self) -> str | None:
        return self._attached

    def attach_event(self, game_state, investigator_id: str,
                     card_id: str | None = None) -> bool:
        """[fast]将手牌中一张非弱点法术事件叠加到黛雅娜（限1张）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._attached is not None:
            return False
        candidates = []
        for cid in inv.hand:
            cd = game_state.get_card_data(cid)
            if cd is None or cd.type != CardType.EVENT:
                continue
            if "spell" not in [t.lower() for t in (cd.traits or [])]:
                continue
            if is_weakness_card(cd):
                continue
            candidates.append(cid)
        if card_id is None:
            card_id = candidates[0] if candidates else None
        if card_id is None or card_id not in candidates:
            return False
        inv.hand.remove(card_id)
        self._attached = card_id
        game_state.log_effect(f"🔮 黛雅娜：叠加【{game_state.card_name(card_id)}】")
        return True

    def play_attached(self, game_state, investigator_id: str) -> str | None:
        """消耗黛雅娜并花费1秘密：把叠加事件放回手牌（会话层随后正常打出）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        if self._attached is None:
            return None
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("secrets", 0) <= 0:
            return None
        inst.exhausted = True
        inst.uses["secrets"] -= 1
        card_id = self._attached
        self._attached = None
        self._awaiting_play = card_id
        inv.hand.append(card_id)
        return card_id

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def track_play(self, ctx):
        """叠加事件被打出：标记待重新叠加。"""
        if self._awaiting_play is not None \
                and ctx.extra.get("card_id") == self._awaiting_play:
            self._played_via_dayana = self._awaiting_play
            self._awaiting_play = None

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def reattach_after_play(self, ctx):
        """打出结算后：事件不入弃牌堆，重新叠加到黛雅娜。"""
        if self._played_via_dayana is None:
            return
        card_id = self._played_via_dayana
        self._played_via_dayana = None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if card_id in inv.discard:
            inv.discard.remove(card_id)
        self._attached = card_id
        ctx.extra["dayana_reattached"] = card_id
        ctx.game_state.log_effect(
            f"🔮 黛雅娜：【{ctx.game_state.card_name(card_id)}】维持叠加")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def drop_attachment(self, ctx):
        """离场：叠加的事件进入持有者弃牌堆。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self._attached is not None:
            inv.discard.append(self._attached)
        self._attached = None
