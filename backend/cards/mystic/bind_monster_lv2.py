"""Bind Monster (Level 2) — Mystic Event.
躲避。这次躲避尝试不使用[agility]，改为使用[willpower]。如果成功并且该敌人为
非[精英]，躲避并将困兽之笼叠加到该敌人。
[reaction]在被叠加的敌人要准备时：检定[willpower](3)。如果成功，叠加敌人不准备。
如果失败，丢弃困兽之笼。

简化说明：
- 打出效果（用意志躲避）由会话层检定后调用 attach_to(enemy_instance_id)。
- "要准备时检定意志(3)"简化为：敌人被就绪时自动重新横置（视为检定成功），
  resolve_ready_test(success) 供会话层做完整检定后结算（失败则丢弃本卡）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BindMonster(CardImplementation):
    card_id = "bind_monster_lv2"

    def attach_to(self, game_state, investigator_id: str, enemy_instance_id: str) -> bool:
        """躲避成功后：将困兽之笼叠加到非精英敌人。"""
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and "elite" in (getattr(enemy_data, "traits", []) or []):
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        scenario.vars["bind_monster_attached"] = enemy_instance_id
        scenario.vars["bind_monster_owner"] = investigator_id
        enemy.exhausted = True
        return True

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def prevent_ready(self, ctx):
        """被叠加的敌人要准备时：保持横置（简化为自动成功）。"""
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return
        enemy_id = scenario.vars.get("bind_monster_attached")
        if not enemy_id or ctx.target != enemy_id:
            return
        enemy = ctx.game_state.get_card_instance(enemy_id)
        if enemy is not None:
            enemy.exhausted = True
            ctx.extra["bind_monster_prevented_ready"] = True

    def resolve_ready_test(self, game_state, success: bool) -> None:
        """完整检定结算：失败则丢弃困兽之笼（敌人正常准备）。"""
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return
        if success:
            return
        enemy_id = scenario.vars.pop("bind_monster_attached", None)
        owner_id = scenario.vars.pop("bind_monster_owner", None)
        owner = game_state.get_investigator(owner_id) if owner_id else None
        if owner is not None:
            owner.discard.append("bind_monster_lv2")
        enemy = game_state.get_card_instance(enemy_id) if enemy_id else None
        if enemy is not None:
            enemy.exhausted = False
