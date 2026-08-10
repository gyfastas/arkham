"""Decorated Skull (Level 0) — Rogue Asset, Accessory slot. (04026)
使用(0充能)。
[反应]在你所在地点有调查员、盟友支援卡或敌人被击败后：将1资源（从供应堆
拿取）放到彩饰骷髅上，视为充能。
[行动]花费1充能：抽取1张卡牌并获得1资源。

简化说明：
- 敌人在你所在地点被击败：被击败时敌人仍在地点/交战区（ENEMY_DEFEATED
  先于移除结算），据此判定"在你所在地点"。
- 盟友支援卡被击败：按卡牌 traits 含 "ally" 且其拥有者在你所在地点判定。
- 数据笔误兼容：JSON 的 uses 键为 "chargess"，首次访问时规整为 "charges"
  （segment_of_onyx 同例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DecoratedSkull(CardImplementation):
    card_id = "decorated_skull_lv0"
    activations = [{
        "id": "spend_charge",
        "label": "花1充能：抽1张牌并获得1资源",
        "method": "spend_charge",
        "actions": 1,
    }]

    def _owner_inv(self, game_state):
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return None
        inv = game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        return inv

    @staticmethod
    def _add_charge(game_state, instance_id) -> None:
        inst = game_state.get_card_instance(instance_id)
        if inst is None:
            return
        if "chargess" in inst.uses:  # 数据笔误兼容
            value = inst.uses.pop("chargess")
            inst.uses.setdefault("charges", value)
        inst.uses["charges"] = inst.uses.get("charges", 0) + 1

    def _at_owner_location(self, ctx, enemy_id: str) -> bool:
        """敌人是否在拥有者所在地点（地点未交战列表或同地调查员交战区）。"""
        inv = self._owner_inv(ctx.game_state)
        if inv is None:
            return False
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and enemy_id in loc.enemies:
            return True
        for other in ctx.game_state.investigators.values():
            if other.location_id == inv.location_id and enemy_id in other.threat_area:
                return True
        return False

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.REACTION)
    def charge_on_enemy_defeated(self, ctx):
        """你所在地点的敌人被击败后：放1充能。"""
        if not ctx.target or not self._at_owner_location(ctx, ctx.target):
            return
        self._add_charge(ctx.game_state, self.instance_id)
        ctx.game_state.log_effect("💀 彩饰骷髅：敌人被击败，获得1充能")

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.REACTION)
    def charge_on_investigator_defeated(self, ctx):
        """你所在地点的调查员被击败后：放1充能。"""
        owner = self._owner_inv(ctx.game_state)
        fallen = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or fallen is None:
            return
        if fallen.location_id != owner.location_id:
            return
        self._add_charge(ctx.game_state, self.instance_id)
        ctx.game_state.log_effect("💀 彩饰骷髅：调查员被击败，获得1充能")

    @on_event(GameEvent.ASSET_DEFEATED, priority=TimingPriority.REACTION)
    def charge_on_ally_defeated(self, ctx):
        """你所在地点的盟友支援卡被击败后：放1充能。"""
        owner = self._owner_inv(ctx.game_state)
        if owner is None or not ctx.target or ctx.target == self.instance_id:
            return
        ally = ctx.game_state.get_card_instance(ctx.target)
        if ally is None:
            return
        cd = ctx.game_state.get_card_data(ally.card_id)
        if cd is None or "ally" not in (cd.traits or []):
            return
        ally_owner = ctx.game_state.get_investigator(ally.owner_id)
        if ally_owner is None or ally_owner.location_id != owner.location_id:
            return
        self._add_charge(ctx.game_state, self.instance_id)
        ctx.game_state.log_effect("💀 彩饰骷髅：盟友被击败，获得1充能")

    def spend_charge(self, game_state, investigator_id: str) -> bool:
        """[行动]花费1充能：抽1张牌并获得1资源。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        if "chargess" in inst.uses:  # 数据笔误兼容
            value = inst.uses.pop("chargess")
            inst.uses.setdefault("charges", value)
        if inst.uses.get("charges", 0) < 1:
            return False
        inst.uses["charges"] -= 1
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        inv.resources += 1
        game_state.log_effect("💀 彩饰骷髅：花费1充能，抽1张牌并获得1资源")
        return True
