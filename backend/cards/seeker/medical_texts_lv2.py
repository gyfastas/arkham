"""Medical Texts (Level 2) — Seeker Asset, Hand slot. (08038)
[行动]：选择你所在地点的一位调查员并检定智力(2)。如果你成功，治愈该调查员
1点伤害（如果你成功且超过难度至少2点，改为治愈2点伤害）。如果你失败，
你必须消耗医学教科书或对该调查员造成1点伤害。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层接线），
  与 lv0 同模式；
- 目标调查员简化为发动者自己（多人局目标选择需会话层传参
  target_investigator_id）；
- 失败二选一自动：未消耗则消耗本卡，已消耗则对该调查员造成1点伤害
  （官方为玩家自选；伤害走 DamageEngine，可被盟友分担、触发击败检查）。
"""

from backend.cards.seeker._selftest import CardSelfTest
from backend.engine.damage import DamageEngine
from backend.models.enums import Skill


class MedicalTextsLv2(CardSelfTest):
    card_id = "medical_texts_lv2"

    activations = [
        {"id": "heal_test", "label": "[行动] 智力(2)检定：成功治1伤（超2治2），"
                                     "失败消耗本卡或受1伤",
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
        success, margin = result
        if success:
            heal = 2 if margin >= 2 else 1
            healed = min(heal, target.damage)
            if healed > 0:
                target.damage -= healed
            game_state.log_effect(f"📕 医学教科书(2级)：检定成功，治愈{healed}点伤害")
            return True

        # 失败：必须消耗本卡或造成1点伤害（自动：优先消耗）
        inst = game_state.get_card_instance(self.instance_id)
        if inst is not None and not inst.exhausted:
            inst.exhausted = True
            game_state.log_effect("📕 医学教科书(2级)：检定失败，消耗医学教科书")
        else:
            DamageEngine(game_state, self._selftest_bus).deal_damage(
                target.investigator_id, damage=1, source=self.instance_id,
            )
            game_state.log_effect("📕 医学教科书(2级)：检定失败，造成1点伤害")
        return True
