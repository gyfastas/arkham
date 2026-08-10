"""Empower Self (Level 2) — Mystic Asset, Arcane slot. (06243)
多重。每副牌组限制1张增强自我（敏锐）。
一个法术槽位可以容纳最多3张增强自我卡牌。
每当有卡牌效果要求你不使用[intellect]、改为使用[willpower]时，你可以忽略
该效果的该方面。
[fast]消耗增强自我：本次检定你+2[intellect]。

简化说明：
- [fast]消耗：boost() 消耗本卡并武装，下一次智力检定+2（SKILL_TEST_ENDS 清除）。
- "忽略意志代替智力"：无通用拦截通道（替换逻辑散落在各卡实现内——引擎缺口）；
  本卡在场时维护 scenario.vars["empower_self_ignore_sub"] 集合供替换类效果查询。
- 多重/单槽3张：槽位引擎不支持同卡叠放（引擎缺口），按普通法术槽占用处理。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

IGNORE_SUB_VAR = "empower_self_ignore_sub"


class EmpowerSelf(CardImplementation):
    card_id = "empower_self_lv2"
    activations = [{
        "id": "boost",
        "label": "[快速]消耗：本次检定+2智力",
        "method": "boost",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        holders = ctx.game_state.scenario.vars.setdefault(IGNORE_SUB_VAR, set())
        holders.add(ctx.investigator_id)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        holders = ctx.game_state.scenario.vars.get(IGNORE_SUB_VAR)
        if holders is not None:
            holders.discard(ctx.investigator_id)

    def boost(self, game_state, investigator_id: str) -> bool:
        """[fast]消耗增强自我：本次检定+2智力。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(2, "empower_self_boost")
        self._armed = False  # 仅本次检定

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
