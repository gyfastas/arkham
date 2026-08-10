"""Pendant of the Queen (Level 0) — Seeker Asset, Accessory slot. (06022)
绑定(一瓣缟玛瑙)。使用(3充能)。如果本卡牌没有充能，将其放在一边，位于
场外，并将放在一边的3张一瓣缟玛瑙混洗入你的牌堆。
[快速]消耗皇后的挂坠并花费1充能：选择一个已揭示地点并选择以下一项 -
移动到该地点、发现该地点的1个线索、自动躲避该地点的一名敌人。

简化说明：
- 三种模式由 activate(mode=..., location_id=..., enemy_instance_id=...)
  指定；缺省：地点取第一个非当前地点的已揭示地点（躲避模式取第一个
  有敌人的已揭示地点），模式默认 "move"，敌人默认该地点第一个；
- 自动躲避：敌人横置、脱离一切交战、置于该地点未交战，发 ENEMY_EVADED；
- 充能耗尽：本卡移出场上放入 scenario.vars["set_aside"]（官方为放在一边
  位于场外），3张一瓣缟玛瑙优先取 set_aside 中已有副本，不足凭空补足
  （绑定卡随卡组带入的登记流程属组牌层，引擎缺口），混洗入牌堆；
- 数据 uses 键兼容双 s 写法（"chargess"），见 seeker/_uses.py；
- 移动不携带交战敌人（引擎 _move 同款简化）。
"""

import random

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_count, uses_spend
from backend.models.enums import GameEvent

_SEGMENT = "segment_of_onyx_lv1"
_SET_ASIDE_VAR = "set_aside"


class PendantOfTheQueen(CardImplementation):
    card_id = "pendant_of_the_queen_lv0"
    activations = [{
        "id": "activate",
        "label": "[快速]消耗+1充能：移动到/发现线索于/自动躲避于一个已揭示地点",
        "method": "activate",
    }]

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def activate(self, game_state, investigator_id: str, mode: str = "move",
                 location_id: str | None = None,
                 enemy_instance_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        location = self._choose_location(game_state, inv, mode, location_id)
        if location is None:
            return False

        if mode == "move":
            effect = lambda: self._do_move(game_state, inv, location)
        elif mode == "discover":
            effect = lambda: self._do_discover(game_state, inv, location)
        elif mode == "evade":
            effect = lambda: self._do_evade(game_state, location, enemy_instance_id)
        else:
            return False

        # 费用先行（快速能力：消耗+1充能）
        if not uses_spend(inst, "charges"):
            return False
        inst.exhausted = True
        if not effect():
            return False

        if uses_count(inst, "charges") <= 0:
            self._set_aside_and_recycle_segments(game_state, inv)
        return True

    # ------------------------------------------------ 模式实现
    def _choose_location(self, game_state, inv, mode, location_id):
        if location_id is not None:
            loc = game_state.get_location(location_id)
            if loc is None or not loc.revealed:
                return None
            return loc
        for loc in game_state.locations.values():
            if not loc.revealed:
                continue
            if mode == "evade":
                if loc.enemies:
                    return loc
            elif loc.location_id != inv.location_id:
                return loc
        return None

    @staticmethod
    def _do_move(game_state, inv, location) -> bool:
        inv.location_id = location.location_id
        game_state.log_effect(
            f"👑 皇后的挂坠：移动到【{location.card_data.name_cn or location.card_data.name}】"
        )
        return True

    def _do_discover(self, game_state, inv, location) -> bool:
        if location.clues <= 0:
            return False
        location.clues -= 1
        inv.clues += 1
        game_state.log_effect("👑 皇后的挂坠：发现该地点的1个线索")
        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CLUE_DISCOVERED,
                investigator_id=inv.investigator_id,
                location_id=location.location_id,
                amount=1,
                source=self.instance_id,
            ))
        return True

    @staticmethod
    def _do_evade(game_state, location, enemy_instance_id) -> bool:
        # 该地点的敌人：未交战者 + 与该地点调查员交战者
        candidates = list(location.enemies)
        for inv in game_state.get_investigators_at_location(location.location_id):
            candidates += [e for e in inv.threat_area if e not in candidates]
        eid = enemy_instance_id or (candidates[0] if candidates else None)
        enemy = game_state.get_card_instance(eid) if eid else None
        if enemy is None:
            return False
        enemy.exhausted = True
        for inv in game_state.investigators.values():
            if eid in inv.threat_area:
                inv.threat_area.remove(eid)
        if eid not in location.enemies:
            location.enemies.append(eid)
        game_state.log_effect("👑 皇后的挂坠：自动躲避该地点的一名敌人")
        return True

    # ------------------------------------------------ 充能耗尽
    def _set_aside_and_recycle_segments(self, game_state, inv) -> None:
        """无充能：本卡放在一边（场外），3张一瓣缟玛瑙混洗入牌堆。"""
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        set_aside = game_state.scenario.vars.setdefault(_SET_ASIDE_VAR, [])
        set_aside.append(self.card_id)

        segments = []
        while len(segments) < 3:
            if _SEGMENT in set_aside:
                set_aside.remove(_SEGMENT)
            segments.append(_SEGMENT)  # 不足时凭空补足（绑定池未登记）
        inv.deck.extend(segments)
        random.shuffle(inv.deck)
        game_state.log_effect(
            "👑 皇后的挂坠：充能耗尽，放在一边；3张一瓣缟玛瑙混洗入牌堆"
        )
