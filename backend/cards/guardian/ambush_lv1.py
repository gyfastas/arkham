"""Ambush (Level 1) — Guardian Event. (03148)
叠加到你所在地点。
如果被叠加的地点没有调查员，丢弃埋伏。
强制 - 有敌人生成在被叠加的地点后：对该敌人造成2点伤害并丢弃埋伏。

简化/缺口说明：
- 与 barricade 一致：叠加关系记录在 scenario.vars["ambush_locations"]
  （{location_id: investigator_id}），事件卡本身结算后入弃牌堆（引擎事件卡
  生命周期，叠加的实体表示未实现）。
- "没有调查员则丢弃"：在调查员离开被叠加地点的移动行动中检查（若离开后
  该地点不再有调查员则丢弃标记）。
- 引擎没有"敌人生成"事件（official_core._spawn_enemy_from_encounter 直接
  落场，不经事件总线），伤害触发实现为公开方法 on_enemy_spawned()，供
  引擎/会话层在敌人生成于某地点后调用（见报告：需要 ENEMY_SPAWNED 事件）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

VAR = "ambush_locations"


class Ambush(CardImplementation):
    card_id = "ambush_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        """打出时：叠加到你所在地点。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        locations = ctx.game_state.scenario.vars.setdefault(VAR, {})
        locations[inv.location_id] = inv.investigator_id
        ctx.extra["ambush_location"] = inv.location_id
        ctx.game_state.log_effect("🪤 埋伏：叠加到当前地点")

    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def discard_when_location_empties(self, ctx):
        """被叠加地点没有调查员时：丢弃埋伏。

        MOVE_ACTION_INITIATED 在移动生效前发出，inv.location_id 仍是出发地；
        若移动者离开后被叠加地点不再有其他调查员，丢弃标记。
        """
        locations = ctx.game_state.scenario.vars.get(VAR, {})
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.location_id not in locations:
            return
        remaining = [
            other for other in ctx.game_state.get_investigators_at_location(inv.location_id)
            if other.investigator_id != inv.investigator_id
        ]
        if remaining:
            return
        locations.pop(inv.location_id, None)
        ctx.extra["ambush_discarded"] = inv.location_id
        ctx.game_state.log_effect("🪤 埋伏：地点没有调查员，丢弃埋伏")

    def on_enemy_spawned(self, game_state, enemy_instance_id, location_id) -> bool:
        """强制 - 敌人生成在被叠加地点后：对其造成2点伤害并丢弃埋伏。

        公开方法：由引擎/会话层在敌人生成流程中调用（引擎暂无生成事件）。
        """
        locations = game_state.scenario.vars.get(VAR, {})
        owner_id = locations.get(location_id)
        if owner_id is None:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        if enemy is None:
            return False
        locations.pop(location_id, None)
        deal_damage_to_enemy(game_state, self._bus, enemy_instance_id, 2,
                             defeated_by=owner_id)
        game_state.log_effect(
            f"🪤 埋伏触发：对【{game_state.card_name(enemy.card_id)}】造成2点伤害")
        return True
