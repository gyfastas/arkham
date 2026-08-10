"""Eavesdrop (Level 0) — Rogue Event. (04027)
选择你所在地点的一名未处于交战状态的敌人。检定[智力](X)，X为所选敌人的
躲避值。如果你成功，你发现所在地点的2个线索。

简化说明：
- 打出时选定目标（可经 ctx.extra["target_enemy_id"] 指定，否则自动选你
  所在地点第一个未交战敌人）并武装；随后由会话层发起一次智力检定——
  本实现在 SKILL_TEST_BEGINS 把难度强制设为 X（引擎支持检定开始时改写
  难度，flashlight 同通道），会话层可按任意难度发起。
- 成功时发现2个线索：地点线索不足2个则有多少拿多少；经 CLUE_DISCOVERED
  （amount=2）通知。
- 武装在 SKILL_TEST_ENDS 清除（若先做了其他检定则失效）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Eavesdrop(CardImplementation):
    card_id = "eavesdrop_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._armed = False
        self._x = 0

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def choose_target(self, ctx):
        """选择你所在地点的一名未交战敌人，记录 X=其躲避值。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return

        target_id = ctx.extra.get("target_enemy_id")
        if target_id is not None and target_id not in loc.enemies:
            return  # 显式目标必须未交战且在你所在地点
        if target_id is None:
            target_id = loc.enemies[0] if loc.enemies else None
        enemy = ctx.game_state.get_card_instance(target_id) if target_id else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None:
            return

        self._armed = True
        self._x = enemy_data.enemy_evade or 0
        ctx.extra["eavesdrop_target"] = target_id
        ctx.extra["eavesdrop_x"] = self._x
        ctx.game_state.log_effect(
            f"👂 窃听：以【{ctx.game_state.card_name(enemy.card_id)}】的躲避值"
            f"{self._x}为难度检定智力")

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def set_difficulty(self, ctx):
        """将这次智力检定的难度设为X。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        ctx.difficulty = self._x

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def discover_two_clues(self, ctx):
        """成功：发现所在地点的2个线索。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return
        taken = min(2, loc.clues)
        if taken <= 0:
            return
        loc.clues -= taken
        inv.clues += taken
        ctx.extra["eavesdrop_clues"] = taken
        ctx.game_state.log_effect(f"👂 窃听：成功，发现{taken}个线索")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CLUE_DISCOVERED,
                investigator_id=ctx.investigator_id,
                location_id=inv.location_id,
                amount=taken,
            ))

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._x = 0
