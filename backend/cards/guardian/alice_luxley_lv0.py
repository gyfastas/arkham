"""Alice Luxley (Level 0) — Guardian Asset, Ally slot. (05151)
你获得+1智力。
[反应]在你发现一条线索后，横置爱丽丝·洛克斯雷：对你所在地点的一名敌人
造成1点伤害。

简化说明：
- "横置对敌人造成1伤害"简化为自动触发：你发现线索后若本卡未横置且同地点
  有敌人，自动横置并对敌人造成1伤害（官方为玩家选择是否发动及目标；
  目标自动选择：优先与你交战的敌人，其次地点上的敌人）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class AliceLuxley(CardImplementation):
    card_id = "alice_luxley_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """在场时 +1 智力。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "alice_luxley_intellect_bonus")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def damage_on_clue(self, ctx):
        """你发现线索后：自动横置，对同地点一名敌人造成1伤害。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        if inst.exhausted:
            return
        target = self._pick_enemy(ctx.game_state, inv)
        if target is None:
            return
        inst.exhausted = True
        deal_damage_to_enemy(ctx.game_state, self._bus, target, 1,
                             defeated_by=inv.investigator_id)
        ctx.extra["alice_luxley_damage"] = target
        enemy = ctx.game_state.get_card_instance(target)
        name = ctx.game_state.card_name(enemy.card_id) if enemy else target
        ctx.game_state.log_effect(f"🕵️ 爱丽丝·洛克斯雷：横置，对【{name}】造成1伤害")

    @staticmethod
    def _pick_enemy(game_state, inv) -> str | None:
        """目标自动选择：优先与你交战的敌人，其次你所在地点的敌人。"""
        if inv.threat_area:
            return inv.threat_area[0]
        location = game_state.get_location(inv.location_id)
        if location is not None and location.enemies:
            return location.enemies[0]
        return None
