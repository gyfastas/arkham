"""Cat Burglar (Level 1) — Rogue Asset, Ally slot.
你获得+1敏捷。
[行动]消耗飞贼：脱离每个与你交战的敌人并移动到一个相连地点。
此行动不触发借机攻击。

简化说明：
- 移动目标自动选择第一个相连地点（官方为玩家自选；待 UI 支持目标选择后扩展）。
- 不触发借机攻击：本能力直接结算移动，不经过会触发借机攻击的行动流程。
"""
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CatBurglar(CardImplementation):
    card_id = "cat_burglar_lv1"
    activations = [{
        "id": "disengage_move",
        "label": "消耗：脱离所有敌人并移至相连地点",
        "method": "activate",
        "actions": 1,
    }]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """Provide +1 agility while in play."""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "cat_burglar_agility")

    def activate(self, game_state, investigator_id: str) -> bool:
        """消耗：脱离每个与你交战的敌人并移动到一个相连地点。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        cur_loc = game_state.get_location(inv.location_id)
        if cur_loc is None:
            return False
        destination = None
        for conn_id in cur_loc.connections or []:
            if conn_id in game_state.locations:
                destination = conn_id
                break
        if destination is None:
            return False
        inst.exhausted = True
        # 脱离每个与你交战的敌人：放回当前地点
        for enemy_iid in list(inv.threat_area):
            inv.threat_area.remove(enemy_iid)
            if enemy_iid not in cur_loc.enemies:
                cur_loc.enemies.append(enemy_iid)
        inv.location_id = destination
        return True
