"""Tooth of Eztli (Level 0) — Seeker Asset, Accessory slot. (04023)
结算诡计卡上的能力时，你获得+1[willpower]和+1[agility]。
[反应]在你结算诡计卡上的能力时技能检定成功后，消耗埃兹特里之牙：
抽1张牌。

简化说明：
- 引擎的检定上下文没有"正在结算诡计卡能力"的标记（引擎缺口）：会话/
  剧本层在发起诡计卡检定前调用 begin_treachery_resolution()，检定结束
  自动复位；加值仅对持有者的意志/敏捷检定生效；
- 反应自动触发（官方为玩家选择是否消耗；消耗无其他代价，取有利分支），
  已横置时不再触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ToothOfEztli(CardImplementation):
    card_id = "tooth_of_eztli_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._resolving_treachery = False

    def begin_treachery_resolution(self) -> None:
        """会话/剧本层：声明接下来的技能检定来自诡计卡上的能力。"""
        self._resolving_treachery = True

    def _ready(self, ctx) -> bool:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def treachery_bonus(self, ctx):
        """结算诡计卡能力时：+1意志、+1敏捷。"""
        if not self._resolving_treachery:
            return
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.AGILITY):
            return
        if not self._ready(ctx):
            return
        ctx.modify_amount(1, "tooth_of_eztli_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def draw_on_success(self, ctx):
        """结算诡计卡能力的检定成功后：消耗本卡，抽1张牌。"""
        if not self._resolving_treachery or not self._ready(ctx):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst.exhausted = True
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.extra["tooth_of_eztli_drew"] = True
        ctx.game_state.log_effect("🦷 埃兹特里之牙：诡计检定成功，消耗抽1张牌")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._resolving_treachery = False
