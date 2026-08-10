"""Mind's Eye (Level 2) — Mystic Asset, Arcane slot x2. (06029)
无数。使用(3秘密)。
[reaction] 当你将检定[intellect]、[combat]或[agility]时，花费1秘密：改为检定
[willpower]。
[fast] 弃掉你手牌中1张心灵之眼：在本张心灵之眼上放置2秘密。

简化说明：
- 反应式替换无选择 UI：自动在"意志高于被检技能"时触发（对玩家有利才花秘密），
  花费1秘密后以意志值替换（同 shrivelling 的值替换通道；已投入图标的技能匹配
  仍按原技能结算——引擎缺口：检定技能类型不可整体改写）。
- 快速能力经 add_secrets() 公开方法由会话层/UI 调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_SUBSTITUTABLE = {Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY}


class MindsEye(CardImplementation):
    card_id = "minds_eye_lv2"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type not in _SUBSTITUTABLE:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("secrets", 0) <= 0:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        if willpower <= base_val:
            return  # 简化：仅在有利时自动触发
        inst.uses["secrets"] -= 1
        ctx.modify_amount(willpower - base_val, f"{self.card_id}_substitute")
        ctx.extra[f"{self.card_id}_substituted"] = True

    def add_secrets(self, game_state, investigator_id: str) -> bool:
        """【快速】弃掉手牌中1张心灵之眼：本张+2秘密。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self.card_id not in inv.hand:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        inst.uses["secrets"] = inst.uses.get("secrets", 0) + 2
        return True
