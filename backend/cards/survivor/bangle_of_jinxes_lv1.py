"""Bangle of Jinxes (Level 1) — Survivor Asset, Accessory slot.
使用(1充能)。
[快速] 花费1充能：本次检定+2技能值。（每次检定限1次。）
[反应] 一名敌人攻击你后：在厄运手镯上放置1充能。

简化说明：
- +2技能值经公开方法 spend() 武装（会话层在快速窗口调用），在下一次
  SKILL_VALUE_DETERMINED 生效；每次检定限1次（_used_this_test 控制）。
- "敌人攻击你后"监听 ENEMY_ATTACKS(AFTER)；借机攻击
  (ATTACK_OF_OPPORTUNITY) 同属敌人攻击但未覆盖（引擎缺口/简化，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BangleOfJinxes(CardImplementation):
    card_id = "bangle_of_jinxes_lv1"
    activations = [{
        "id": "spend",
        "label": "快速：花1充能，本次检定+2技能值",
        "method": "spend",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0
        self._used_this_test = False

    def spend(self, game_state, investigator_id: str) -> bool:
        """快速：花费1充能，本次检定+2技能值（每次检定限1次）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if self._used_this_test or inst.uses.get("charges", 0) < 1:
            return False
        inst.uses["charges"] -= 1
        self._armed += 2
        self._used_this_test = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(self._armed, "bangle_of_jinxes_boost")
        self._armed = 0

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.AFTER)
    def recharge_after_attack(self, ctx):
        """一名敌人攻击你后：放置1充能。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != ctx.investigator_id:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        inst.uses["charges"] = inst.uses.get("charges", 0) + 1
        ctx.game_state.log_effect("🧿 厄运手镯：敌人攻击你，放置1充能")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0
        self._used_this_test = False
