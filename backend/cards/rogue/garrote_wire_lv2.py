"""Garrote Wire (Level 2) — Rogue Asset. (06280)
[快速]在你的回合中，消耗绞索：攻击。本次攻击你+2战斗。只能对剩余生命
恰好为1的敌人使用。

简化说明：
- activate() 消耗本卡并武装（校验目标剩余生命==1，仅你的回合）；随后由
  会话层发起战斗行动（weapon_instance_id 传本卡实例）。
- "快速"：activations 声明 actions=0，行动费由会话层执行。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class GarroteWire(CardImplementation):
    card_id = "garrote_wire_lv2"
    activations = [{
        "id": "fight",
        "label": "消耗：攻击剩余生命恰好为1的敌人（+2战斗）",
        "method": "activate",
        "actions": 0,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._enemy_id: str | None = None
        self._my_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_start(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        self._my_turn = inst is not None and inst.owner_id == ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.owner_id == ctx.investigator_id:
            self._my_turn = False

    def activate(self, game_state, investigator_id: str,
                 enemy_instance_id: str | None = None) -> bool:
        """消耗：对剩余生命恰好为1的敌人发起+2战斗的攻击（仅你的回合）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if not self._my_turn:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id) if enemy_instance_id else None
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None or enemy_data.enemy_health is None:
            return False
        if enemy_data.enemy_health - enemy.damage != 1:
            return False  # 只能对剩余生命恰好为1的敌人使用
        inst.exhausted = True
        self._armed = True
        self._enemy_id = enemy_instance_id
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击+2战斗。"""
        if not self._armed or ctx.source != self.instance_id:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(2, "garrote_wire_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._enemy_id = None
