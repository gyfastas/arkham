"""Antiquary (Level 3) — Seeker Asset. (08124)
使用(2资源)。每轮开始时补充这些资源。
古董商上的资源可用于支付[[恩惠]]、[[圣物]]或[[仪式]]卡牌。
[快速]在一张[[恩惠]]、[[圣物]]或[[仪式]]卡牌的技能检定中，花费古董商上
1资源：本次检定你获得+1技能值。

简化说明：
- "可用于支付……卡牌"的跨卡支付通道为引擎缺口（actions._play 的费用结算
  无钩子），见报告；卡上资源目前仅服务于本卡的[快速]能力；
- [快速]能力经 spend_resource() 武装（UI/会话层调用），在下一次
  SKILL_VALUE_DETERMINED 时若检定来源卡（ctx.source）带对应特性则+1；
  未命中特性的检定不消耗武装（资源已花不退，与 ResourceSkillBoost 一致）；
- 数据 uses 键兼容双 s 写法（"resourcess"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_key, uses_spend
from backend.models.enums import GameEvent, TimingPriority

FULL_RESOURCES = 2


class Antiquary(CardImplementation):
    card_id = "antiquary_lv3"
    paid_traits: tuple[str, ...] = ("favor", "relic", "ritual")
    activations = [{
        "id": "spend",
        "label": "[快速]花古董商上1资源：对应特性卡的检定+1技能值",
        "method": "spend_resource",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def replenish(self, ctx):
        """每轮开始时：补充至2资源。"""
        holder = self._find_holder(ctx.game_state)
        if holder is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.uses[uses_key(inst, "resources")] = FULL_RESOURCES

    def spend_resource(self, game_state, investigator_id: str) -> bool:
        """[快速]花1卡上资源：下一次对应特性卡的技能检定+1（可叠加武装）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or not uses_spend(inst, "resources"):
            return False
        self._armed += 1
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """检定来源卡带对应特性时：每次武装+1技能值。"""
        if not self._armed:
            return
        holder = self._find_holder(ctx.game_state)
        if holder is None or holder.investigator_id != ctx.investigator_id:
            return
        if not self._source_matches(ctx):
            return  # 非对应特性卡的检定：不消耗武装
        ctx.modify_amount(self._armed, f"{self.card_id}_boost")
        ctx.extra[f"{self.card_id}_boost"] = self._armed
        self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0

    def _source_matches(self, ctx) -> bool:
        """检定来源卡（ctx.source 实例）是否带任一对应特性。"""
        if ctx.source is None:
            return False
        inst = ctx.game_state.get_card_instance(ctx.source)
        cd = ctx.game_state.get_card_data(inst.card_id) if inst else None
        traits = [t.lower() for t in (cd.traits or [])] if cd else []
        return any(t in traits for t in self.paid_traits)

    def _find_holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None
