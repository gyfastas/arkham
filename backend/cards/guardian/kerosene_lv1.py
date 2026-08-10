"""Kerosene (Level 1) — Guardian Asset. (04304)
使用(3补给)。如果煤油没有补给，弃置它。
[行动]如果本轮有敌人在此地点被击败，横置煤油并花费1补给：
在你所在地点的调查员和[[盟友]]支援卡之间治愈合计至多2点恐惧。

简化说明：
- "本轮有敌人在此地点被击败"由本卡跟踪：ENEMY_DEFEATED 时按敌人所在
  地点（交战敌人取交战调查员所在地点）记录，ROUND_BEGINS 清空。
- 治愈分配自动选择：按恐惧从多到少依次治愈同地点的调查员，再治愈同地点
  带恐惧的盟友；可经 activate(allocations=[("investigator_id"|instance_id, n)])
  指定（官方为玩家自由分配"至多2点"）。
- 数据修正：卡牌数据 uses 键为 "suppliess"（源数据笔误），读取时两键兼容。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, TimingPriority

_SUPPLIES_KEYS = ("supplies", "suppliess")  # 数据键笔误兼容


def _get_supplies(inst) -> int:
    for key in _SUPPLIES_KEYS:
        if key in inst.uses:
            return inst.uses[key]
    return 0


def _spend_supply(inst) -> bool:
    for key in _SUPPLIES_KEYS:
        if key in inst.uses and inst.uses[key] > 0:
            inst.uses[key] -= 1
            return True
    return False


class Kerosene(CardImplementation):
    card_id = "kerosene_lv1"
    activations = [{
        "id": "heal",
        "label": "[行动] 横置+1补给：同地点治愈至多2恐惧（需本轮此地有敌人被击败）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._defeated_locations: set[str] = set()

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def track_defeat(self, ctx):
        """记录本轮敌人被击败的地点。"""
        enemy_iid = ctx.target
        if enemy_iid is None:
            return
        # 未交战敌人：在地点的 enemies 列表里
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                self._defeated_locations.add(loc.location_id)
                return
        # 交战敌人：交战调查员的所在地点
        for inv in ctx.game_state.investigators.values():
            if enemy_iid in inv.threat_area:
                self._defeated_locations.add(inv.location_id)
                return
        # 兜底：击败者所在地点
        defeater = ctx.game_state.get_investigator(ctx.investigator_id)
        if defeater is not None and defeater.location_id:
            self._defeated_locations.add(defeater.location_id)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def clear_round(self, ctx):
        self._defeated_locations.clear()

    def activate(self, game_state, investigator_id: str,
                 allocations: list | None = None) -> bool:
        """[行动] 横置+1补给：同地点治愈至多2点恐惧。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted or _get_supplies(inst) <= 0:
            return False
        if inv.location_id not in self._defeated_locations:
            return False

        plan = allocations if allocations is not None else \
            self._auto_allocations(game_state, inv)
        healed = self._apply_heals(game_state, plan)
        if healed <= 0:
            return False

        inst.exhausted = True
        _spend_supply(inst)
        game_state.log_effect(f"🛢️ 煤油：治愈同地点合计{healed}点恐惧")
        if _get_supplies(inst) <= 0:
            self._discard_self(game_state, inv)
            game_state.log_effect("🛢️ 煤油：补给耗尽，弃置")
        return True

    @staticmethod
    def _auto_allocations(game_state, inv) -> list:
        """自动分配至多2点治愈：同地点调查员（恐惧多者优先）→ 盟友。"""
        plan = []
        remaining = 2
        investigators = sorted(
            game_state.get_investigators_at_location(inv.location_id),
            key=lambda i: -i.horror,
        )
        for other in investigators:
            take = min(remaining, other.horror)
            if take > 0:
                plan.append((other.investigator_id, take))
                remaining -= take
        if remaining > 0:
            for other in game_state.get_investigators_at_location(inv.location_id):
                for iid in other.play_area:
                    ci = game_state.get_card_instance(iid)
                    cd = game_state.get_card_data(ci.card_id) if ci else None
                    if cd is None or "ally" not in (cd.traits or []):
                        continue
                    take = min(remaining, ci.horror)
                    if take > 0:
                        plan.append((iid, take))
                        remaining -= take
                if remaining <= 0:
                    break
        return plan

    @staticmethod
    def _apply_heals(game_state, plan) -> int:
        healed = 0
        for target_id, amount in (plan or [])[:]:
            amount = max(0, min(int(amount), 2 - healed))
            if amount <= 0:
                continue
            target_inv = game_state.get_investigator(target_id)
            if target_inv is not None:
                actual = min(amount, target_inv.horror)
                target_inv.horror -= actual
                healed += actual
                continue
            ci = game_state.get_card_instance(target_id)
            if ci is not None:
                actual = min(amount, ci.horror)
                ci.horror -= actual
                healed += actual
        return healed

    def _discard_self(self, game_state, inv) -> None:
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
