"""Crisis of Identity (Level 0) — Neutral Treachery, Signature Weakness (Lola Hayes).
显现：丢弃你控制的所有你当前角色的卡牌。然后，丢弃你牌堆顶的1张卡牌。
将你的角色切换到该丢弃卡牌的职阶（若丢弃的是弱点，切换为中立角色）。

简化说明：
- 萝拉的"角色"没有引擎级状态，按阵营字符串存放在
  scenario.vars["role_{investigator_id}"]（缺省 "neutral"）；improvisation_lv0
  及会话层读写同一键。
- "你控制的卡牌"指在场卡牌（play_area）；手牌不受影响。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card


def role_key(investigator_id: str) -> str:
    return f"role_{investigator_id}"


class CrisisOfIdentity(CardImplementation):
    card_id = "crisis_of_identity_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "crisis_of_identity_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "crisis_of_identity_lv0" in inv.hand:
            inv.hand.remove("crisis_of_identity_lv0")

        scenario = ctx.game_state.scenario
        role = scenario.vars.get(role_key(inv.investigator_id), "neutral")

        # 丢弃你控制的所有当前角色的卡牌
        discarded = []
        for iid in list(inv.play_area):
            inst = ctx.game_state.get_card_instance(iid)
            cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
            if cd is not None and cd.card_class.value == role:
                inv.play_area.remove(iid)
                ctx.game_state.cards_in_play.pop(iid, None)
                inv.discard.append(inst.card_id)
                discarded.append(inst.card_id)

        # 丢弃牌堆顶1张，切换到其职阶（弱点→中立）
        top = None
        if inv.deck:
            top = inv.deck.pop(0)
            inv.discard.append(top)
            cd = ctx.game_state.get_card_data(top)
            if cd is None or is_weakness_card(cd):
                new_role = "neutral"
            else:
                new_role = cd.card_class.value
            scenario.vars[role_key(inv.investigator_id)] = new_role

        inv.discard.append("crisis_of_identity_lv0")
        ctx.extra["crisis_of_identity"] = {
            "old_role": role,
            "discarded_in_play": discarded,
            "top_card": top,
            "new_role": scenario.vars.get(role_key(inv.investigator_id), role),
        }
        ctx.game_state.log_effect(
            f"🎭 身分危机：丢弃{len(discarded)}张【{role}】卡牌，角色切换为"
            f"【{ctx.extra['crisis_of_identity']['new_role']}】"
        )
