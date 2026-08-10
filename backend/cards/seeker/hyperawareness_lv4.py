"""Hyperawareness (Level 4) — Seeker Asset. (07264)
使用(2资源)。当每轮开始时重新补满这些资源。
[快速]花费你的资源池或超感知的1资源：这次技能检定你+1智力或+1敏捷。

简化说明：
- 加值/叠加机制与 lv0 共用 ResourceSkillBoost（UI/会话层经 spend() 调用）；
- 支付来源：spend(..., from_card=True)（默认）优先扣本卡上的资源标记，
  耗尽后回落资源池；from_card=False 直接扣资源池（官方为玩家自选来源）；
- 每轮开始（ROUND_BEGINS）将本卡资源补满至2；
- 数据 uses 键兼容双 s 写法（"resourcess"），见 seeker/_uses.py。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.cards.seeker._uses import uses_count, uses_key
from backend.models.enums import GameEvent, Skill, TimingPriority

_MAX_STORED = 2


class HyperawarenessLv4(ResourceSkillBoost):
    card_id = "hyperawareness_lv4"
    boosted_skills = (Skill.INTELLECT, Skill.AGILITY)

    def spend(self, game_state, investigator_id: str, skill: Skill,
              from_card: bool = True) -> bool:
        """花费1资源（默认优先扣本卡上的资源标记）：本次检定+1对应技能。"""
        if skill not in self.boosted_skills:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False

        if from_card and uses_count(inst, "resources") >= 1:
            inst.uses[uses_key(inst, "resources")] -= 1
        else:
            if inv.resources < 1:
                return False
            inv.resources -= 1
        self._armed[skill] = self._armed.get(skill, 0) + 1
        return True

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def replenish(self, ctx):
        """每轮开始：本卡上的资源补满至2。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        key = uses_key(inst, "resources")
        if inst.uses.get(key, 0) < _MAX_STORED:
            inst.uses[key] = _MAX_STORED
