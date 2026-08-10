"""Improvisation (Level 0) — Neutral Event, Signature (Lola Hayes).
快速。只能在你回合中打出。
切换你的角色。直到你回合结束，你所选角色的下一张卡牌资源费用降低3点。抽1张牌。

简化说明：
- 萝拉的"角色"存放在 scenario.vars["role_{investigator_id}"]（缺省
  "neutral"），与 crisis_of_identity_lv0 共用；新角色由会话层经
  ctx.extra["new_role"] 传入，缺省时保持原角色。
- "下一张角色卡费用-3"通过 get_cost_discount() 表达；引擎打出费用通道
  （actions._play）目前不查询折扣——需要引擎/会话侧接线。折扣在回合结束
  或首次使用时清除。
- "只能在你回合中打出"由会话层出牌校验负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def _role_key(investigator_id: str) -> str:
    return f"role_{investigator_id}"


def _discount_key(investigator_id: str) -> str:
    return f"improvisation_discount_{investigator_id}"


class Improvisation(CardImplementation):
    card_id = "improvisation_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "improvisation_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        scenario = ctx.game_state.scenario

        # 切换角色（新角色由会话层选择并传入 extra["new_role"]）
        new_role = ctx.extra.get("new_role")
        if new_role:
            scenario.vars[_role_key(inv.investigator_id)] = new_role

        # 直到回合结束：下一张角色卡资源费用-3
        scenario.vars[_discount_key(inv.investigator_id)] = 3

        # 抽1张牌
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))

        ctx.extra["improvisation_role"] = scenario.vars.get(
            _role_key(inv.investigator_id), "neutral"
        )
        ctx.game_state.log_effect(
            f"🎭 即兴表演：角色切换为【{ctx.extra['improvisation_role']}】，"
            "下一张角色卡费用-3，抽1张牌"
        )

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_discount(self, ctx):
        ctx.game_state.scenario.vars.pop(_discount_key(ctx.investigator_id), None)

    def get_cost_discount(self, game_state, investigator_id, card_id) -> int:
        """下一张当前角色卡的费用折扣（3）；首次查询即视为使用并清除。"""
        scenario = game_state.scenario
        if not scenario.vars.get(_discount_key(investigator_id)):
            return 0
        cd = game_state.get_card_data(card_id)
        role = scenario.vars.get(_role_key(investigator_id), "neutral")
        if cd is None or cd.card_class.value != role:
            return 0
        scenario.vars.pop(_discount_key(investigator_id), None)
        return 3
