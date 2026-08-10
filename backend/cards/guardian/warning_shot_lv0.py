"""Warning Shot (Level 0) — Guardian Event. (05229)
作为打出鸣枪示警的额外费用，花费你控制的1张[[枪械]]支援卡的1子弹。
移动你所在地点所有非[[精英]]敌人到一个连接地点。此行动不会引起趁乱攻击。

简化说明：
- 弹药来源：默认你装备区第一把有弹药的枪械；可用
  ctx.extra["ammo_source_instance"] 指定（必须是你控制且有弹药的枪械）。
  无枪械/无弹药时额外费用无法支付：效果不结算（官方为不能打出；引擎已
  完成打出流程，资源费不退，注明）。
- 目的地：默认地点 connections 第一个连接地点；可用
  ctx.extra["destination"] 指定（须为连接地点）。所有非精英敌人移往同一
  连接地点（含你威胁区/同地点调查员威胁区/地点上未交战的），移动后
  变为未交战状态。
- "此行动不引起趁乱攻击"：CARD_PLAYED 先于 AoO 发出，武装一次性豁免
  （同 mano_a_mano_lv0 模式）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class WarningShot(CardImplementation):
    card_id = "warning_shot_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._aoo_free = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def fire_warning(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 额外费用：花1弹药
        firearm = self._choose_firearm(ctx, inv)
        if firearm is None:
            ctx.extra["warning_shot_fizzle"] = True
            ctx.game_state.log_effect(
                "🔫 鸣枪示警：无法控制有弹药的枪械，额外费用无法支付，效果不结算")
            return
        firearm.uses["ammo"] -= 1

        loc = ctx.game_state.get_location(inv.location_id)
        dest_id = ctx.extra.get("destination")
        if loc is None or not loc.connections:
            ctx.extra["warning_shot_fizzle"] = True
            return
        if dest_id not in loc.connections:
            dest_id = loc.connections[0]
        dest = ctx.game_state.get_location(dest_id)
        if dest is None:
            ctx.extra["warning_shot_fizzle"] = True
            return

        # 移动所有非精英敌人（交战与未交战）到连接地点
        moved = []
        for eid in list(loc.enemies):
            if self._is_non_elite(ctx, eid):
                loc.enemies.remove(eid)
                dest.enemies.append(eid)
                moved.append(eid)
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            for eid in list(other.threat_area):
                if self._is_non_elite(ctx, eid):
                    other.threat_area.remove(eid)
                    if eid not in dest.enemies:
                        dest.enemies.append(eid)
                    moved.append(eid)

        ctx.extra["warning_shot_moved"] = moved
        ctx.extra["warning_shot_destination"] = dest_id
        ctx.game_state.log_effect(
            f"🔫 鸣枪示警：{len(moved)}个非精英敌人被移动到连接地点")

        # 此行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    @staticmethod
    def _is_non_elite(ctx, instance_id: str) -> bool:
        inst = ctx.game_state.get_card_instance(instance_id)
        data = ctx.game_state.get_card_data(inst.card_id) if inst else None
        if data is None or data.type != CardType.ENEMY:
            return False
        return not is_elite_enemy(data)

    def _choose_firearm(self, ctx, inv):
        """你控制且有弹药的枪械；可用 ammo_source_instance 指定。"""
        def usable(iid: str):
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None or ci.uses.get("ammo", 0) <= 0:
                return None
            cd = ctx.game_state.get_card_data(ci.card_id)
            traits = {t.lower() for t in (getattr(cd, "traits", []) or [])} if cd else set()
            if "firearm" not in traits:
                return None
            return ci

        source_iid = ctx.extra.get("ammo_source_instance")
        if source_iid is not None:
            if source_iid not in inv.play_area:
                return None
            return usable(source_iid)
        for iid in inv.play_area:
            ci = usable(iid)
            if ci is not None:
                return ci
        return None

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        """打出本卡的行动不引起趁乱攻击。"""
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
