"""Dig Deep (Level 4) — Survivor Asset.
使用(2资源)。每轮开始时重新补满这些资源。
[快速] 花费你资源池或深挖上的1资源：本次检定+1[意志]或+1[敏捷]。

简化说明：
- 资源键名兼容数据文件的 "resourcess" 笔误与标准 "resources"。
- 花费优先扣深挖上的资源，用尽后扣调查员资源池（官方为玩家选择来源，
  可经 from_card=True/False 指定）；加值在下一次 SKILL_VALUE_DETERMINED
  生效，可叠加（同 ResourceSkillBoost）。
- 每轮开始（ROUND_BEGINS）将深挖上的资源补满至2。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_PRINTED_RESOURCES = 2


class DigDeepLv4(ResourceSkillBoost):
    card_id = "dig_deep_lv4"
    boosted_skills = (Skill.WILLPOWER, Skill.AGILITY)

    def _card_resources(self, inst) -> int:
        return inst.uses.get("resources", inst.uses.get("resourcess", 0))

    def spend(self, game_state, investigator_id: str, skill: Skill,
              from_card: bool | None = None) -> bool:
        """花费1资源（深挖上的优先）：本次检定+1意志或+1敏捷（可叠加）。"""
        if skill not in self.boosted_skills:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False

        key = "resources" if "resources" in inst.uses else "resourcess"
        on_card = inst.uses.get(key, 0)
        if from_card is True and on_card < 1:
            return False
        if from_card is None or from_card is True:
            if on_card >= 1:
                inst.uses[key] -= 1
                self._armed[skill] = self._armed.get(skill, 0) + 1
                return True
        if from_card is False and inv.resources < 1:
            return False
        if inv.resources < 1:
            return False
        inv.resources -= 1
        self._armed[skill] = self._armed.get(skill, 0) + 1
        return True

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def replenish(self, ctx):
        """每轮开始：补满深挖上的2个资源。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = "resources" if "resources" in inst.uses else "resourcess"
        if inst.uses.get(key, 0) < _PRINTED_RESOURCES:
            inst.uses[key] = _PRINTED_RESOURCES
            ctx.game_state.log_effect("🕳️ 深挖：每轮开始，补满2个资源")
