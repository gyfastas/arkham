"""Medical Texts (Level 0) — Seeker Asset, Hand slot.
[行动]：选择你所在地点的一名调查员并检定智力(2)。如果成功，治愈该调查员
1点伤害。如果失败，对该调查员造成1点伤害。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线）；
- 目标调查员简化为发动者自己（多人局目标选择需会话层传参）；
- 失败伤害走 DamageEngine（可被盟友分担、触发击败检查）。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.engine.damage import DamageEngine
from backend.models.enums import Skill


class MedicalTexts(CardSelfTest):
    card_id = "medical_texts_lv0"

    activations = [
        {"id": "heal_test", "label": "[行动] 智力(2)检定：成功治1伤，失败受1伤",
         "method": "activate", "actions": 1},
    ]

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        result = self.run_self_test(
            game_state, investigator_id, Skill.INTELLECT, 2,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if success:
            if target.damage > 0:
                target.damage -= 1
                game_state.log_effect("📕 医学教科书：检定成功，治愈1点伤害")
        else:
            DamageEngine(game_state, self._selftest_bus).deal_damage(
                target.investigator_id, damage=1, source=self.instance_id,
            )
            game_state.log_effect("📕 医学教科书：检定失败，造成1点伤害")
        return True
