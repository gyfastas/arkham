"""Bruiser (Level 3) — Guardian Asset. (08122)
使用(2资源)。每轮开始时补充这些资源。
好勇斗狠身上的资源可用于支付[[Armor]]、[[Firearm]]或[[Melee]]卡牌的费用。
[快速]在一张[[Armor]]、[[Firearm]]或[[Melee]]卡牌的技能检定中，花费好勇斗狠身上
的1资源：本次检定你获得+1技能值。

简化说明：
- 检定加值：spend()（会话层/UI 经 activations 调用）从卡上扣1资源并武装；
  下一次 SKILL_VALUE_DETERMINED 若检定来源卡（ctx.source）带有
  armor/firearm/melee 特质则 +1 技能值（可叠加，与 ResourceSkillBoost 同模式）。
- 每轮开始补充：ROUND_BEGINS 时将卡上资源补至印刷值2。
- "卡上资源可用于支付卡牌费用"：引擎出牌费用通道只扣调查员资源池，
  无第三方支付通道——引擎缺口，未实现（见报告）。
- 数据 uses 键兼容 "resources"/"resourcess"（抓取复数化瑕疵）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_TRAITS = {"armor", "firearm", "melee"}
_PRINTED_RESOURCES = 2


class Bruiser(CardImplementation):
    card_id = "bruiser_lv3"
    activations = [{
        "id": "boost",
        "label": "花卡上1资源：武器/护甲检定+1技能值",
        "method": "spend",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0

    @staticmethod
    def _key(inst) -> str:
        if "resources" in inst.uses:
            return "resources"
        return "resourcess" if "resourcess" in inst.uses else "resources"

    def spend(self, game_state, investigator_id: str) -> bool:
        """从本卡花费1资源：本次技能检定+1技能值（限武器/护甲检定）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        key = self._key(inst)
        if inst.uses.get(key, 0) <= 0:
            return False
        inst.uses[key] -= 1
        self._armed += 1
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """武装的加值应用到武器/护甲卡牌的检定上。"""
        if self._armed <= 0:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        source_inst = ctx.game_state.get_card_instance(ctx.source) if ctx.source else None
        source_data = (
            ctx.game_state.get_card_data(source_inst.card_id) if source_inst else None
        )
        traits = set(getattr(source_data, "traits", None) or [])
        if not traits & _TRAITS:
            return
        count = self._armed
        self._armed = 0
        ctx.modify_amount(count, "bruiser_boost")
        ctx.game_state.log_effect(f"🥊 好勇斗狠：本次检定+{count}技能值")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        # 未消耗的武装状态在检定结束后清除（资源已花不退）
        self._armed = 0

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def replenish(self, ctx):
        """每轮开始时：将本卡资源补至2。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = self._key(inst)
        if inst.uses.get(key, 0) < _PRINTED_RESOURCES:
            inst.uses[key] = _PRINTED_RESOURCES
            ctx.game_state.log_effect("🥊 好勇斗狠：每轮开始，资源补充至2")
