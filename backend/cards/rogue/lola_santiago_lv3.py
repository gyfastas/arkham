"""Lola Santiago (Level 3) — Rogue Asset, Ally slot. (04196)
你+1智力、+1敏捷。
[快速]消耗萝拉·圣地亚哥并花费X资源：在你所在地点发现1个线索。X为你
所在地点的隐蔽值。

简化说明：
- 被动加值经 SKILL_VALUE_DETERMINED 通道（同 peter_sylvestre）。
- activate() 为公开方法（activations 声明快速0行动），校验隐蔽值费用、
  消耗并发现1线索（地点无线索时仍可发动但无效果）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class LolaSantiago(CardImplementation):
    card_id = "lola_santiago_lv3"
    activations = [{
        "id": "discover",
        "label": "消耗+花X资源(X=隐蔽值)：发现1线索",
        "method": "activate",
        "actions": 0,
    }]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def passive_boost(self, ctx):
        """你+1智力、+1敏捷。"""
        if ctx.skill_type not in (Skill.INTELLECT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "lola_santiago_passive")

    def activate(self, game_state, investigator_id: str) -> bool:
        """[快速]消耗并花费X资源（X=所在地隐蔽值）：发现1个线索。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
        x = loc.shroud
        if inv.resources < x:
            return False
        inv.resources -= x
        inst.exhausted = True
        if loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            from backend.engine.event_bus import EventContext
            bus = getattr(self, "_bus", None)
            if bus is not None:
                bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CLUE_DISCOVERED,
                    investigator_id=investigator_id,
                    location_id=inv.location_id,
                    amount=1,
                ))
        game_state.log_effect("🔍 萝拉·圣地亚哥：发现1个线索")
        return True

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
