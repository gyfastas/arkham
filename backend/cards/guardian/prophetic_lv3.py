"""Prophetic (Level 3) — Guardian Asset. (08120)
使用(2资源)。当每轮开始时重新补满这些资源。
先知先觉上的资源可以被用来支付[[幸运]]、[[法术]]或[[勇气]]卡牌。
[fast]在[[幸运]]、[[法术]]或[[勇气]]卡牌上的技能检定中，从先知先觉花费1资源：
你这次检定+1技能值。

实现说明：
- 数据 JSON 的 uses 键为 "resourcess"（笔误），入场时归一化为 "resources"。
- spend() / pay_for_card() 由会话层调用（均为[fast]自由窗口）；技能加值经
  武装后在下次 SKILL_VALUE_DETERMINED 生效，检定结束清除。
- 特征门限（Fortune/Spell/Spirit）由会话层校验；spend() 接受可选
  test_card_id 做防御性校验。

本文件同时定义 Sleuth (08121) 的共享基类 TraitResourceTalent。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TraitResourceTalent(CardImplementation):
    """"每轮补满N资源 + 花资源为特定特征检定+1技能值"人才的共享基类。"""

    card_id = ""
    payable_traits: tuple[str, ...] = ()
    max_resources = 2

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0

    # ---- 资源管理 ----

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def normalize_uses(self, ctx):
        """入场：归一化 uses 键（数据笔误 resourcess → resources）。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if "resourcess" in inst.uses:
            inst.uses["resources"] = inst.uses.pop("resourcess")
        inst.uses.setdefault("resources", self.max_resources)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def replenish(self, ctx):
        """每轮开始时补满资源。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if "resourcess" in inst.uses:
            inst.uses["resources"] = inst.uses.pop("resourcess")
        inst.uses["resources"] = self.max_resources

    # ---- 启动能力（会话层调用） ----

    def spend(self, game_state, investigator_id: str,
              test_card_id: str | None = None) -> bool:
        """[fast] 从本卡花费1资源：本次（特征匹配的）检定+1技能值。"""
        if test_card_id is not None:
            data = game_state.get_card_data(test_card_id)
            traits = set(getattr(data, "traits", None) or [])
            if not traits & set(self.payable_traits):
                return False
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.uses.get("resources", 0) < 1:
            return False
        inst.uses["resources"] -= 1
        self._armed += 1
        return True

    def pay_for_card(self, game_state, investigator_id: str, amount: int) -> bool:
        """从本卡资源支付特征匹配卡牌的费用（会话层结算费用时调用）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if amount < 0 or inst.uses.get("resources", 0) < amount:
            return False
        if amount:
            inst.uses["resources"] -= amount
        return True

    # ---- 检定加值 ----

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(self._armed, f"{self.card_id}_boost")
        self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0


class Prophetic(TraitResourceTalent):
    card_id = "prophetic_lv3"
    payable_traits = ("fortune", "spell", "spirit")
