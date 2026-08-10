"""Delilah O'Rourke (Level 3) — Rogue Asset, Ally slot. (06281)
你获得+1战斗和+1敏捷。
[快速]消耗黛利拉·欧鲁尔克并花费X资源：选择你所在地点的一名敌人。对所选
敌人造成1点伤害（如果该敌人已横置，改为2点伤害）。X为所选敌人的躲避值。

简化说明：
- 伤害经 _shared.deal_damage_to_enemy 直接结算（不走 DAMAGE_DEALT 修改
  窗口，与 dynamite_blast 等直接伤害一致）。
- 目标由会话层传入（activations 声明 target: enemy）；activate 校验敌人
  在你所在地点（未交战列表或同地任一调查员交战区）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import GameEvent, Skill, TimingPriority


class DelilahORourke(CardImplementation):
    card_id = "delilah_orourke_lv3"
    activations = [{
        "id": "damage",
        "label": "[快速]消耗+花X资源（X=目标躲避值）：造成1伤害（已横置改2）",
        "method": "activate",
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """+1战斗和+1敏捷（在场期间）。"""
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "delilah_skill_bonus")

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """[快速]消耗并花费X资源：对所选敌人造成1伤害（已横置改2）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        # 目标：你所在地点的敌人
        loc = game_state.get_location(inv.location_id)
        candidates: list[str] = []
        if loc is not None:
            candidates.extend(loc.enemies)
        for other in game_state.investigators.values():
            if other.location_id == inv.location_id:
                candidates.extend(other.threat_area)
        enemy_id = target_instance_id or (candidates[0] if candidates else None)
        if enemy_id is None or enemy_id not in candidates:
            return False
        enemy = game_state.get_card_instance(enemy_id)
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None:
            return False

        x = enemy_data.enemy_evade or 0
        if inv.resources < x:
            return False
        inv.resources -= x
        inst.exhausted = True

        amount = 2 if enemy.exhausted else 1
        deal_damage_to_enemy(
            game_state, self._bus, enemy_id, amount,
            defeated_by=investigator_id,
        )
        game_state.log_effect(
            f"🕵️ 黛利拉·欧鲁尔克：花费{x}资源，对【{game_state.card_name(enemy.card_id)}】"
            f"造成{amount}点伤害")
        return True
