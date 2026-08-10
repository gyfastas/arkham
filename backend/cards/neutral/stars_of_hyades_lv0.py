"""Stars of Hyades (Level 0) — Neutral Treachery, Signature Weakness (Sefina Rousseau).
显现：随机选择赛菲娜·卢梭下的一张事件卡，将其从游戏中移除。若不能，受到
1点伤害和1点恐惧。若你的牌组有5张或以上卡牌，不要丢弃毕宿星团，改为将其
重洗回你的牌组。

简化说明：
- "赛菲娜·卢梭下的卡牌"没有引擎级存储，按 card_id 列表存放在
  scenario.vars["beneath_{investigator_id}"]（与 the_painted_world_lv0 共用），
  由会话层/赛菲娜能力写入。
- 移出游戏的牌记录在 scenario.vars["removed_from_game"]（引擎无独立移除区，
  与 abandoned_and_alone 同一惯例）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class StarsOfHyades(CardImplementation):
    card_id = "stars_of_hyades_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "stars_of_hyades_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "stars_of_hyades_lv0" in inv.hand:
            inv.hand.remove("stars_of_hyades_lv0")

        scenario = ctx.game_state.scenario
        beneath = scenario.vars.setdefault(beneath_key(inv.investigator_id), [])
        events = [
            cid for cid in beneath
            if (cd := ctx.game_state.get_card_data(cid)) is not None
            and cd.type == CardType.EVENT
        ]
        removed = None
        if events:
            removed = random.choice(events)
            beneath.remove(removed)
            scenario.vars.setdefault("removed_from_game", []).append(removed)
            ctx.game_state.log_effect(
                f"✨ 毕宿星团：【{ctx.game_state.card_name(removed)}】从游戏中移除"
            )
        else:
            inv.damage += 1  # 直接伤害/恐惧（不分配）
            inv.horror += 1
            ctx.game_state.log_effect("✨ 毕宿星团：赛菲娜下无事件，受到1点伤害和1点恐惧")

        # 牌组≥5张：重洗回牌组而非丢弃
        if len(inv.deck) >= 5:
            inv.deck.append("stars_of_hyades_lv0")
            random.shuffle(inv.deck)
            shuffled_back = True
        else:
            inv.discard.append("stars_of_hyades_lv0")
            shuffled_back = False

        ctx.extra["stars_of_hyades"] = {
            "removed": removed,
            "shuffled_back": shuffled_back,
        }
