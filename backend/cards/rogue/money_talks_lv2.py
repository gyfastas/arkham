"""Money Talks (Level 2) — Rogue Event. (08054)
快速。在任意地点的一位调查员发起技能检定时打出。
本次检定不使用原指定技能（[willpower]/[intellect]/[combat]/[agility]），
改为资源检定。执行检定的调查员本次检定基础技能值等同于你资源池中资源
数量的一半（向下取整）。抽1张牌。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：任意调查员发起检定时，
  若持有者资源//2 高于执行者的原基础技能值（严格有利）则自动打出
  （费用0），持有者抽1张牌。
- 基础值替换经 SKILL_VALUE_DETERMINED 改写（保留图标/标记/其他加值）；
  "资源检定"仅为叙事差异，引擎检定类型不变（列为简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MoneyTalksLv2(CardImplementation):
    card_id = "money_talks_lv2"
    persistent_in_hand = True  # 在手牌中持续监听检定发起窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed: tuple[str, int] | None = None  # (tester_id, base)

    def _find_holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.card_id in inv.hand:
                return inv
        return None

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def auto_play(self, ctx):
        holder = self._find_holder(ctx.game_state)
        tester = ctx.game_state.get_investigator(ctx.investigator_id)
        if holder is None or tester is None:
            return
        half = holder.resources // 2
        if half <= tester.get_skill(ctx.skill_type):
            return  # 无收益时不自动打出（简化策略）
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 0) or 0) if cd else 0
        if holder.resources < cost:
            return
        holder.resources -= cost
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)
        if holder.deck:
            holder.hand.append(holder.deck.pop(0))
        self._armed = (ctx.investigator_id, half)
        ctx.extra["money_talks_lv2_base"] = half
        ctx.game_state.log_effect(
            f"💵 金钱万能：执行者基础技能值改为{half}，持有者抽1张牌")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_base(self, ctx):
        if self._armed is None or self._armed[0] != ctx.investigator_id:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            return
        ctx.modify_amount(self._armed[1] - base, "money_talks_lv2_substitute")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = None
