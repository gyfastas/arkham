"""Money Talks (Level 0) — Rogue Event. (05029)
快速。在你发起技能检定时打出。
本次检定不使用原指定技能（[willpower]/[intellect]/[combat]/[agility]），
改为资源检定。本次检定你的基础技能值等同于你资源池中资源数量的一半
（向下取整）。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：发起检定时若 资源//2 高于
  你的原基础技能值（严格有利）则自动打出（费用0）。
- 基础值替换经 SKILL_VALUE_DETERMINED 改写（保留图标/标记/其他加值）；
  "资源检定"仅为叙事差异，引擎检定类型不变（敌方加成等按原技能结算，
  列为简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MoneyTalks(CardImplementation):
    card_id = "money_talks_lv0"
    persistent_in_hand = True  # 在手牌中持续监听检定发起窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_base: int | None = None

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def auto_play(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        half = inv.resources // 2
        if half <= inv.get_skill(ctx.skill_type):
            return  # 无收益时不自动打出（简化策略）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 0) or 0) if cd else 0
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._armed_base = half
        ctx.extra["money_talks_base"] = half
        ctx.game_state.log_effect(
            f"💵 金钱万能：基础技能值改为资源一半（{half}）")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_base(self, ctx):
        if self._armed_base is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            return
        ctx.modify_amount(self._armed_base - base, "money_talks_substitute")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_base = None
