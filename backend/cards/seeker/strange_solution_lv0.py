"""Strange Solution (Level 0) — Seeker Asset.
[行动]：检定智力(4)。如果成功，丢弃奇怪的溶液，并抽取2张卡牌。
在冒险日志中，记录下"你已确认溶液的成分"。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- "冒险日志"记录在 scenario.vars["campaign_log"]。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import Skill


class StrangeSolution(CardSelfTest):
    card_id = "strange_solution_lv0"

    activations = [
        {"id": "identify", "label": "[行动] 智力(4)检定：成功则弃掉本卡并抽2张",
         "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]：检定智力(4)；成功则结算 resolve()。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, 4,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if success:
            self.resolve(game_state, investigator_id, True)
        return True

    def resolve(self, game_state, investigator_id: str, success: bool) -> bool:
        """结算[intellect](4)检定结果。成功：丢弃本卡、抽2张牌、记录日志。"""
        if not success:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False

        # 丢弃奇怪的溶液
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inst is not None:
            game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("strange_solution_lv0")

        # 抽取2张卡牌
        for _ in range(2):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))

        # 冒险日志记录
        scenario = getattr(game_state, "scenario", None)
        if scenario is not None:
            log = scenario.vars.setdefault("campaign_log", [])
            if "确认溶液成分" not in log:
                log.append("确认溶液成分")
        return True
