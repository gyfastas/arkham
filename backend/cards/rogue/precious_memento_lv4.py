"""Precious Memento (Level 4) — Rogue Asset. (08115)
每副牌组限制1张。
[reaction] 在你技能检定失败且低于难度至少2点后，消耗珍贵记忆：治愈其1点恐惧。
[reaction] 在你技能检定成功且超过难度至少2点后，消耗珍贵记忆：治愈其1点伤害。

简化说明：
- 两个反应均为自动触发：仅在珍贵记忆上确有可治愈的恐惧/伤害时才消耗
  （无东西可治时触发无收益，避免无谓横置；官方为玩家自行选择）。
- "每副牌组限制1张"为牌组构建规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class PreciousMemento(CardImplementation):
    card_id = "precious_memento_lv4"

    def _ready_instance(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return None
        return inst

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.REACTION)
    def heal_horror_on_fail(self, ctx):
        """失败且低于难度至少2点：消耗，治愈本卡1点恐惧。"""
        inst = self._ready_instance(ctx)
        if inst is None or inst.horror <= 0:
            return
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin < 2:
            return
        inst.exhausted = True
        inst.horror -= 1
        ctx.extra["precious_memento_healed_horror"] = True
        ctx.game_state.log_effect("🧸 珍贵记忆：检定失败2点以上，消耗并治愈其1点恐惧")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def heal_damage_on_success(self, ctx):
        """成功且超过难度至少2点：消耗，治愈本卡1点伤害。"""
        inst = self._ready_instance(ctx)
        if inst is None or inst.damage <= 0:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        inst.exhausted = True
        inst.damage -= 1
        ctx.extra["precious_memento_healed_damage"] = True
        ctx.game_state.log_effect("🧸 珍贵记忆：检定成功2点以上，消耗并治愈其1点伤害")
