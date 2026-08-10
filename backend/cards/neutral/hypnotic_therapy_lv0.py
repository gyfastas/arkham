"""Hypnotic Therapy (Level 0) — Neutral Asset. Carolyn Fern 专属。
[action] 横置催眠疗法：检定[intellect](2)。若成功，治愈你所在地点一位
调查员的1点恐惧。然后，该调查员可抽1张牌。
[reaction] 在你的其他卡牌效果治愈一位调查员的恐惧后，横置催眠疗法：
该效果额外治愈1点恐惧。

简化说明：
- [action] 实现为 activate()（参照 duke_lv0：由会话层调用，内部跑智力
  检定）；治愈目标默认本人，可传 target_investigator_id（须同地点）；
  "可抽1张牌"简化为自动抽取。
- [reaction] 无"治愈恐惧"引擎事件（引擎缺口），实现为公开方法
  amplify_heal()，由会话层在其他效果治愈时调用。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import Skill


class HypnoticTherapy(CardImplementation):
    card_id = "hypnotic_therapy_lv0"
    activations = [{
        "id": "activate",
        "label": "[行动] 横置：智力(2)检定，成功治愈1恐惧并抽1牌",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        """横置：智力(2)检定，成功则治愈同地点1位调查员1恐惧，其抽1牌。"""
        inst = game.state.get_card_instance(self.instance_id)
        inv = game.state.get_investigator(investigator_id)
        if inst is None or inv is None or inst.exhausted:
            return False
        target_id = target_investigator_id or investigator_id
        target = game.state.get_investigator(target_id)
        if target is None or target.location_id != inv.location_id:
            return False

        inst.exhausted = True

        def on_success(result):
            target.horror = max(0, target.horror - 1)
            if target.deck:
                target.hand.append(target.deck.pop(0))
            game.state.log_effect(
                f"🛋️ 催眠疗法：治愈 {target_id} 1点恐惧，其抽1张牌"
            )

        game.skill_test_engine.run_test(
            investigator_id=investigator_id,
            skill_type=Skill.INTELLECT,
            difficulty=2,
            on_success=on_success,
        )
        return True

    def amplify_heal(self, game_state, investigator_id: str,
                     target_investigator_id: str) -> bool:
        """[reaction] 横置：另一效果治愈恐惧时，额外治愈1点恐惧。"""
        inst = game_state.get_card_instance(self.instance_id)
        target = game_state.get_investigator(target_investigator_id)
        if inst is None or inst.exhausted or target is None:
            return False
        inst.exhausted = True
        target.horror = max(0, target.horror - 1)
        game_state.log_effect(
            f"🛋️ 催眠疗法：额外治愈 {target_investigator_id} 1点恐惧"
        )
        return True
