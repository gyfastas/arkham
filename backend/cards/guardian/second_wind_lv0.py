"""Second Wind (Level 0) — Guardian Event. (04149)
只可作为你的第一个行动打出。治愈1点伤害(如果你本轮抽出了1张诡计卡，
改为治愈2点伤害)。然后，抽取1张卡牌。

简化说明：
- "第一个行动"：以 actions_remaining >= 3 近似判定（同 mano_a_mano 约定）。
- "本轮抽出了诡计卡"由手牌中的持续注册实例跟踪（persistent_in_hand）：
  监听 ENCOUNTER_CARD_DRAWN（遭遇牌堆诡计）与 CARD_DRAWN（牌库诡计），
  记录于 scenario.vars，ROUND_BEGINS 清除。
- 打出时持久实例与临时实例都会收到 CARD_PLAYED，经 ctx.extra 去重只结算一次。
- 抽牌直接操作牌库顶（不经 CARD_DRAWN 钩子，避免递归触发弱点显现）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_VAR = "second_wind_drew_treachery"


class SecondWind(CardImplementation):
    card_id = "second_wind_lv0"
    persistent_in_hand = True  # 手牌中持续跟踪本轮诡计抽取

    # ---- 跟踪：本轮谁抽过诡计卡 ----

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.AFTER)
    def track_encounter_treachery(self, ctx):
        card_id = ctx.extra.get("card_id")
        cd = ctx.game_state.get_card_data(card_id) if card_id else None
        if cd is not None and cd.type == CardType.TREACHERY:
            drawn = ctx.game_state.scenario.vars.setdefault(_VAR, [])
            if ctx.investigator_id not in drawn:
                drawn.append(ctx.investigator_id)

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def track_deck_treachery(self, ctx):
        card_id = ctx.extra.get("card_id")
        cd = ctx.game_state.get_card_data(card_id) if card_id else None
        if cd is not None and cd.type == CardType.TREACHERY:
            drawn = ctx.game_state.scenario.vars.setdefault(_VAR, [])
            if ctx.investigator_id not in drawn:
                drawn.append(ctx.investigator_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def reset_round(self, ctx):
        ctx.game_state.scenario.vars.pop(_VAR, None)

    # ---- 打出结算 ----

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        """第一个行动：治愈1伤害（本轮抽过诡计则2），然后抽1张牌。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.extra.get("second_wind_resolved"):
            return  # 持久实例与临时实例去重
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.actions_remaining < 3:
            ctx.extra["second_wind_fizzle"] = True
            ctx.game_state.log_effect("🌬️ 恢复元气：不是本回合第一个行动，效果不结算")
            return
        ctx.extra["second_wind_resolved"] = True

        drew_treachery = ctx.investigator_id in ctx.game_state.scenario.vars.get(_VAR, [])
        heal = 2 if drew_treachery else 1
        healed = min(heal, inv.damage)
        inv.damage -= healed

        drawn = None
        if inv.deck:
            drawn = inv.deck.pop(0)
            inv.hand.append(drawn)

        ctx.extra["second_wind_healed"] = healed
        ctx.extra["second_wind_drew"] = drawn
        ctx.game_state.log_effect(
            f"🌬️ 恢复元气：治愈{healed}点伤害，抽取1张卡牌")
