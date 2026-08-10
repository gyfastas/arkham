"""Family Inheritance (Level 0) — Neutral Asset, Permanent (Preston Fairmont deck only).
[行动]：将本卡上的所有资源移动到你的资源池。
强制 - 当你的回合开始时：在本卡上放置4个资源（来自标记池）。本卡上的资源
可以像在你的资源池中一样被花费。你的回合结束时，丢弃本卡上的所有资源。

简化说明：
- 卡上资源存放在实例 uses["resources"]。
- "像资源池一样花费"：引擎的花费路径不咨询卡牌（引擎缺口），提供
  spend() 公开方法供会话层优先扣卡上资源。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

RESOURCES_PER_TURN = 4


class FamilyInheritance(CardImplementation):
    card_id = "family_inheritance_lv0"
    activations = [{
        "id": "collect",
        "label": "[行动] 将卡上资源移入资源池",
        "method": "activate",
        "actions": 1,
    }]

    def _find_card(self, game_state):
        inst = game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.card_id == "family_inheritance_lv0":
            return inst
        return None

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def place_resources(self, ctx):
        """你的回合开始时：在本卡上放置4个资源。"""
        inst = self._find_card(ctx.game_state)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        inst.uses["resources"] = inst.uses.get("resources", 0) + RESOURCES_PER_TURN
        ctx.extra["family_inheritance_placed"] = RESOURCES_PER_TURN

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def discard_resources(self, ctx):
        """你的回合结束时：丢弃本卡上的所有资源。"""
        inst = self._find_card(ctx.game_state)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        if inst.uses.get("resources", 0):
            inst.uses["resources"] = 0
            ctx.extra["family_inheritance_discarded"] = True

    def activate(self, game_state, investigator_id) -> bool:
        """[行动]：将本卡上的所有资源移动到你的资源池。"""
        inv = game_state.get_investigator(investigator_id)
        inst = self._find_card(game_state)
        if inv is None or inst is None or investigator_id != inst.owner_id:
            return False
        amount = inst.uses.get("resources", 0)
        if amount <= 0:
            return False
        inst.uses["resources"] = 0
        inv.resources += amount
        game_state.log_effect(f"💰 家族遗产：{amount}资源移入资源池")
        return True

    def spend(self, game_state, investigator_id, amount: int) -> bool:
        """像资源池一样花费卡上资源（会话层调用）。"""
        inst = self._find_card(game_state)
        if inst is None or investigator_id != inst.owner_id:
            return False
        if inst.uses.get("resources", 0) < amount:
            return False
        inst.uses["resources"] -= amount
        return True
