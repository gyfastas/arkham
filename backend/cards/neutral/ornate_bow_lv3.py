"""Ornate Bow (Level 3) — Neutral Asset, 2 Hand slots. (04204)
使用（1弹药）。华丽长弓上至多放置1弹药。
[action]花费1弹药：战斗。本次攻击使用[敏捷]代替[战斗]。本次攻击你获得+2[敏捷]
并造成+2伤害。
[action]：你搭上另一支箭。在华丽长弓上放置1弹药。

简化说明：
- 卡面无弹药时无法以其发起攻击（攻击动作的费用即1弹药），实现在
  FIGHT_ACTION_INITIATED：无弹药则取消该次攻击（引擎支持 cancel）。
- 敏捷代替战斗：modify_amount(敏捷-战斗+2)（同 shrivelling 的换算惯例）。
- +2伤害经 ctx.extra["bonus_damage"] 通道汇入战斗结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class OrnateBow(CardImplementation):
    card_id = "ornate_bow_lv3"
    activations = [
        {"id": "reload", "label": "[行动] 搭上箭：放置1弹药", "method": "activate_reload", "actions": 1},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    # ------------------------------------------------------------------
    # 装填
    # ------------------------------------------------------------------
    def activate_reload(self, game_state, investigator_id: str) -> bool:
        """[action]：在华丽长弓上放置1弹药（至多1）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.uses.get("ammo", 0) >= 1:
            return False
        inst.uses["ammo"] = 1
        return True

    # ------------------------------------------------------------------
    # 攻击
    # ------------------------------------------------------------------
    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_on_attack(self, ctx):
        """以本弓攻击：花费1弹药作为攻击费用；无弹药则无法攻击。"""
        self._armed = False
        if ctx.source != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("ammo", 0) <= 0:
            ctx.cancel()  # 无弹药：不能以此弓发起攻击
            return
        inst.uses["ammo"] -= 1
        self._armed = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_substitute(self, ctx):
        """本次攻击使用敏捷代替战斗，并+2敏捷。"""
        if not self._armed or ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        delta = inv.get_skill(Skill.AGILITY) - inv.get_skill(Skill.COMBAT) + 2
        ctx.modify_amount(delta, "ornate_bow_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """攻击成功：+2伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if not self._armed or ctx.source != self.instance_id:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 2

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
