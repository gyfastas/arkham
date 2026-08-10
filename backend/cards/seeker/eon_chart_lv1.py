"""Eon Chart (Level 1) — Seeker Asset, Accessory slot. (08098)
使用(3秘密)。
[快速]在你的回合中，横置万古图表并花费1秘密：选择并执行以下行动中的一项
（移动、躲避或调查）。

简化说明：
- "执行一项行动"为简化执行（卡实现拿不到 ActionResolver——引擎缺口，见
  报告）：移动=直接移到连接地点（自动取第一个连接，destination= 可指定）；
  调查=经 CardSelfTest 回放智力检定（无投入窗口），成功发现1条线索；
  躲避=回放敏捷检定，成功则目标敌人横置并解除交战；
- "你的回合中"经 INVESTIGATOR_TURN_BEGINS/ENDS 跟踪；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.cards.seeker._uses import uses_spend
from backend.models.enums import GameEvent, Skill, TimingPriority

ALLOWED_ACTIONS = ("move", "evade", "investigate")


class EonChart(CardSelfTest):
    card_id = "eon_chart_lv1"
    actions_per_use = 1  # lv4 覆盖为 2
    activations = [{
        "id": "extra_action",
        "label": "[快速]横置+1秘密：执行移动/躲避/调查中的一项",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._my_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def turn_begins(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            self._my_turn = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def turn_ends(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            self._my_turn = False

    def activate(self, game_state, investigator_id: str,
                 actions: list[str] | None = None,
                 destination: str | None = None,
                 enemy_instance_id: str | None = None) -> bool:
        """[快速]横置+1秘密：执行1项（lv4为2项不同）移动/躲避/调查。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        if not self._my_turn:
            return False
        if actions is None:
            actions = ["move"]
        if len(actions) != self.actions_per_use:
            return False
        if any(a not in ALLOWED_ACTIONS for a in actions):
            return False
        if len(set(actions)) != len(actions):
            return False  # lv4：两项必须不同
        if not uses_spend(inst, "secrets"):
            return False
        inst.exhausted = True

        done = []
        for action in actions:
            if action == "move":
                done.append(self._do_move(game_state, inv, destination))
            elif action == "investigate":
                done.append(self._do_investigate(game_state, inv))
            elif action == "evade":
                done.append(self._do_evade(game_state, inv,
                                           enemy_instance_id))
        game_state.log_effect(
            f"⏳ 万古图表：横置+1秘密，执行{','.join(actions)}"
        )
        return any(done)

    def _do_move(self, game_state, inv, destination) -> bool:
        loc = game_state.get_location(inv.location_id)
        connections = list(getattr(loc, "connections", []) or [])
        if destination is None:
            destination = connections[0] if connections else None
        if destination is None or destination not in connections:
            return False
        inv.location_id = destination
        return True

    def _do_investigate(self, game_state, inv) -> bool:
        loc = game_state.get_location(inv.location_id)
        if loc is None:
            return False
        result = self.run_self_test(
            game_state, inv.investigator_id, Skill.INTELLECT, loc.shroud,
            source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if success and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            self._emit_clue_discovered(game_state, inv, loc)
        return success

    def _do_evade(self, game_state, inv, enemy_instance_id) -> bool:
        if enemy_instance_id is None:
            engaged = game_state.get_engaged_enemies(inv.investigator_id)
            enemy_instance_id = engaged[0].instance_id if engaged else None
        if enemy_instance_id is None:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or data is None:
            return False
        result = self.run_self_test(
            game_state, inv.investigator_id, Skill.AGILITY,
            data.enemy_evade or 0, source=self.instance_id,
        )
        if result is None:
            return False
        success, _margin = result
        if success:
            enemy.exhausted = True
            if enemy_instance_id in inv.threat_area:
                inv.threat_area.remove(enemy_instance_id)
            loc = game_state.get_location(inv.location_id)
            if loc is not None and enemy_instance_id not in loc.enemies:
                loc.enemies.append(enemy_instance_id)
        return success

    def _emit_clue_discovered(self, game_state, inv, loc) -> None:
        bus = getattr(self, "_selftest_bus", None)
        if bus is None:
            return
        from backend.engine.event_bus import EventContext
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CLUE_DISCOVERED,
            investigator_id=inv.investigator_id,
            location_id=loc.location_id,
            amount=1,
        ))
