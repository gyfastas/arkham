"""Counterespionage (Level 1) — Rogue Event. (08049)
快速。在你抽取一张非弱点诡计卡时打出。
取消该卡牌的显现效果并抽取遭遇牌堆顶部的卡牌。
[反应]在你打出反间谍活动时，提升其费用2点：将"遭遇牌堆"换成"你的牌堆"。
[反应]在你打出反间谍活动时，提升其费用2点：将"你"换成"任一位调查员"。

简化说明：
- 从手牌中自动触发（a_test_of_will 同模式；官方为玩家选择时机）：你抽到
  非弱点诡计卡时，若手牌有本卡且资源足够，自动打出、标记
  scenario.vars["cancelled_encounter"]，由会话层跳过显现结算。
- 两个[反应]加费升级为玩家可选项，自动触发时默认不启用；可经
  ctx.extra["counterespionage_boost_deck"]（改抽自己牌堆顶）与
  ["counterespionage_boost_any"]（可为任一调查员的抽牌打出）启用，
  每项额外+2费用。
- "抽取遭遇牌堆顶部的卡牌"：弹出牌堆顶并发出 ENCOUNTER_CARD_DRAWN
  （extra["via"]="counterespionage"），显现结算由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card

_BASE_COST = 2
_BOOST_COST = 2


class Counterespionage(CardImplementation):
    card_id = "counterespionage_lv1"
    persistent_in_hand = True  # 在手牌中持续监听诡计抽取窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_and_draw(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id or ctx.extra.get("counterespionage_cancelled"):
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.TREACHERY:
            return
        if is_weakness_card(cd) or "weakness" in (cd.traits or []):
            return

        boost_any = bool(ctx.extra.get("counterespionage_boost_any"))
        boost_deck = bool(ctx.extra.get("counterespionage_boost_deck"))
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if drawer is None:
            return

        # 持有者：默认为抽牌者本人；升级后可替任一调查员取消
        holder = None
        if self.card_id in drawer.hand:
            holder = drawer
        elif boost_any:
            for cand in ctx.game_state.investigators.values():
                if self.card_id in cand.hand:
                    holder = cand
                    break
        if holder is None:
            return

        cost = _BASE_COST + _BOOST_COST * (int(boost_any) + int(boost_deck))
        if holder.resources < cost:
            return
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 取消显现效果（会话层据此跳过结算）
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["counterespionage_cancelled"] = card_id
        ctx.game_state.log_effect(
            f"🕵️ 反间谍活动：取消【{ctx.game_state.card_name(card_id)}】的显现效果")

        # 抽取遭遇牌堆顶（升级后改抽自己牌堆顶）
        if boost_deck:
            if holder.deck:
                holder.hand.append(holder.deck.pop(0))
                ctx.extra["counterespionage_drew_own"] = True
                ctx.game_state.log_effect("🕵️ 反间谍活动：抽取你的牌堆顶1张牌")
            return
        encounter_deck = ctx.game_state.scenario.encounter_deck
        if not encounter_deck or self._bus is None:
            return
        drawn = encounter_deck.pop(0)
        ctx.extra["counterespionage_drew_encounter"] = drawn
        ctx.game_state.log_effect(
            f"🕵️ 反间谍活动：抽取遭遇牌堆顶——【{ctx.game_state.card_name(drawn)}】")
        from backend.engine.event_bus import EventContext
        self._bus.emit(EventContext(
            game_state=ctx.game_state,
            event=GameEvent.ENCOUNTER_CARD_DRAWN,
            investigator_id=holder.investigator_id,
            extra={"card_id": drawn, "via": "counterespionage"},
        ))
