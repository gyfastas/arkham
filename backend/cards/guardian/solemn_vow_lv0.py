"""Solemn Vow (Level 0) — Guardian Asset. (06020)
多重。快速。打出庄严立誓到你所在地点另一位调查员的控制之下。
[fast]如果庄严立誓的所有者位于你所在地点，消耗庄严立誓：将你控制的卡牌上
的1点伤害或恐惧移动到该调查员控制的卡牌上。

简化说明：
- "打出到另一位调查员控制下"由会话层负责（实例 owner_id 为牌组持有者，
  controller_id 为控制者，本卡进控制者装备区）。
- 转移能力为公开方法 activate_transfer()，由控制者启动：默认从控制者本人
  移1点伤害到所有者本人；可经参数指定恐惧或其他卡牌实例（须分别由控制者
  /所有者控制）。
"""

from backend.cards.base import CardImplementation


class SolemnVow(CardImplementation):
    card_id = "solemn_vow_lv0"
    activations = [{
        "id": "transfer",
        "label": "消耗：转移1点伤害/恐惧给所有者",
        "method": "activate_transfer",
        "actions": 0,
    }]

    def activate_transfer(
        self,
        game_state,
        controller_id: str,
        horror: bool = False,
        from_instance_id: str | None = None,
        to_instance_id: str | None = None,
    ) -> bool:
        """[fast] 消耗：从控制者控制的卡移1点伤害/恐惧到所有者控制的卡。"""
        controller = game_state.get_investigator(controller_id)
        inst = game_state.get_card_instance(self.instance_id)
        if controller is None or inst is None:
            return False
        if self.instance_id not in controller.play_area or inst.exhausted:
            return False
        owner = game_state.get_investigator(inst.owner_id)
        if owner is None or owner.location_id != controller.location_id:
            return False

        # 来源/目标：缺省为控制者/所有者本人，可为双方控制的支援卡实例
        if from_instance_id is None:
            source = controller
        else:
            source = game_state.get_card_instance(from_instance_id)
            if source is None or from_instance_id not in controller.play_area:
                return False
        if to_instance_id is None:
            target = owner
        else:
            target = game_state.get_card_instance(to_instance_id)
            if target is None or to_instance_id not in owner.play_area:
                return False

        amount = source.horror if horror else source.damage
        if amount < 1:
            return False

        inst.exhausted = True
        if horror:
            source.horror -= 1
            target.horror += 1
        else:
            source.damage -= 1
            target.damage += 1
        kind = "恐惧" if horror else "伤害"
        game_state.log_effect(
            f"🤝 庄严立誓：消耗，将1点{kind}转移给 {owner.investigator_id}")
        return True
