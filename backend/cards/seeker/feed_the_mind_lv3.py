"""Feed the Mind (Level 3) — Seeker Asset. (04267)
使用(3秘密)。[行动]消耗养神术并花费1秘密：检定智力(0)。你成功且每超过
难度1点，抽取1张卡牌。然后，你手牌每超出上限1张，受到1点恐惧。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- 抽牌直接自牌堆顶抽取（不发 CARD_DRAWN，与 cryptic_research 一致；
  抽到弱点不触发揭示，已知简化）；
- 手牌上限取引擎常量 HAND_SIZE_LIMIT=8（Laboratory Assistant 等修正
  仅作用于 upkeep 手牌检查，本卡不感知）。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.cards.seeker._uses import uses_spend
from backend.engine.phase_upkeep import HAND_SIZE_LIMIT
from backend.models.enums import Skill


class FeedTheMind(CardSelfTest):
    card_id = "feed_the_mind_lv3"
    activations = [{
        "id": "feed",
        "label": "[行动]消耗+1秘密：智力(0)检定，每超1点抽1张",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        # 费用先行：消耗 + 花费1秘密（无论检定成败）
        if not uses_spend(inst, "secrets"):
            return False
        inst.exhausted = True

        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, 0,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, margin = result
        drawn = 0
        if success:
            for _ in range(max(0, margin)):
                if not inv.deck:
                    break
                inv.hand.append(inv.deck.pop(0))
                drawn += 1
            if drawn:
                game_state.log_effect(f"🧠 养神术：超难度{margin}点，抽取{drawn}张卡牌")
        else:
            game_state.log_effect("🧠 养神术：检定失败")

        # "然后"段无论成败均结算（失败即抽0张后检查）
        excess = max(0, len(inv.hand) - HAND_SIZE_LIMIT)
        if excess:
            inv.horror += excess
            game_state.log_effect(f"🧠 养神术：手牌超上限{excess}张，受到{excess}点恐惧")
        return True
