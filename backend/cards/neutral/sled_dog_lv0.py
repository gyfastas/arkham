"""Sled Dog (Level 0) — Neutral Asset, Ally slot. (08127)
你的牌组中至多可包含4张雪橇犬。至多2张雪橇犬卡占用1个盟友槽位。
[action]横置X只雪橇犬：移动。移动X次。
[action]横置X只雪橇犬：战斗。本次攻击你获得+X[战斗]。本次攻击不造成标准
伤害，改为造成X点伤害。

简化说明：
- 4张牌组上限与"2只犬占1个盟友槽"为构筑/槽位规则：槽位管理器不支持
  半槽计数，列为引擎缺口，由卡组校验与会话层负责。
- 横置范围：由持有者控制的所有雪橇犬实例（可多只同时在场）。
- 移动能力：activate_move() 只完成横置付费，X次移动的目的地选择由会话层
  逐次执行（引擎 MOVE 需要目的地）。
- 战斗能力：activate_fight() 横置并武装；+X战斗经 SKILL_VALUE_DETERMINED，
  X点伤害经 bonus_damage = X-1（标准伤害1的差额）通道汇入战斗结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SledDog(CardImplementation):
    card_id = "sled_dog_lv0"
    activations = [
        {"id": "move", "label": "[行动] 横置X只雪橇犬：移动X次", "method": "activate_move", "actions": 1},
        {"id": "fight", "label": "[行动] 横置X只雪橇犬：战斗，+X战斗、X伤害", "method": "activate_fight", "actions": 1},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._fight_x = 0

    def _available_dogs(self, game_state, inv) -> list:
        """持有者控制下未横置的雪橇犬实例。"""
        dogs = []
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == "sled_dog_lv0" and not inst.exhausted:
                dogs.append(inst)
        return dogs

    def _exhaust_dogs(self, game_state, investigator_id, x: int):
        inv = game_state.get_investigator(investigator_id)
        if inv is None or x < 1:
            return None
        dogs = self._available_dogs(game_state, inv)
        if len(dogs) < x:
            return None
        for inst in dogs[:x]:
            inst.exhausted = True
        return inv

    def activate_move(self, game_state, investigator_id, x: int = 1) -> bool:
        """[action] 横置X只雪橇犬：移动X次（移动本身由会话层逐次执行）。"""
        return self._exhaust_dogs(game_state, investigator_id, x) is not None

    def activate_fight(self, game_state, investigator_id, x: int = 1) -> bool:
        """[action] 横置X只雪橇犬：武装一次 +X战斗、X伤害 的攻击。"""
        if self._exhaust_dogs(game_state, investigator_id, x) is None:
            return False
        self._fight_x = x
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if self._fight_x <= 0 or ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(self._fight_x, "sled_dog_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def damage_override(self, ctx):
        """不造成标准伤害，改为X点伤害：bonus_damage = X-1。"""
        if self._fight_x <= 0 or ctx.source != self.instance_id:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + (self._fight_x - 1)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._fight_x = 0
