"""Hospital Debts — Neutral Treachery, Signature Weakness ("Skids" O'Toole).
揭示：放入你的威胁区域。
[free]将你资源池中的1个资源移到医院欠债上。（每轮限制2次。）
强制 - 游戏结束时，如果医院欠债上的资源少于6个：你在本次冒险中少获得2点经验。

简化说明：
- free 能力实现为 activate() 公开方法，由会话层/UI 调用。
- 游戏结束的经验惩罚由 game_end_penalty() 提供给会话层结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HospitalDebts(CardImplementation):
    card_id = "hospital_debts"
    activations = [{"id": "pay", "label": "放1资源到医院欠债（每轮限2）", "method": "activate"}]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._paid_this_round = 0

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "hospital_debts":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "hospital_debts" in inv.hand:
            inv.hand.remove("hospital_debts")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="hospital_debts",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ci.uses = {"resources": 0}
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        self._paid_this_round = 0

    def activate(self, game_state, investigator_id) -> bool:
        """[free]将1个资源移到医院欠债上（每轮限2次）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if self._paid_this_round >= 2:
            return False
        debts = self._find_debts(game_state, inv)
        if debts is None:
            return False
        inv.resources -= 1
        debts.uses["resources"] = debts.uses.get("resources", 0) + 1
        self._paid_this_round += 1
        # 付清6个资源后弃掉医院欠债
        if debts.uses["resources"] >= 6:
            self._discard(game_state, inv, debts)
        return True

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束结算：资源少于6个则少获得2点经验。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        debts = self._find_debts(game_state, inv)
        if debts is not None and debts.uses.get("resources", 0) < 6:
            return "医院欠债未付清：本次冒险少获得2点经验"
        return None

    @staticmethod
    def _find_debts(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "hospital_debts":
                return inst
        return None

    @staticmethod
    def _discard(game_state, inv, inst):
        if inst.instance_id in inv.threat_area:
            inv.threat_area.remove(inst.instance_id)
        inv.discard.append(inst.card_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
