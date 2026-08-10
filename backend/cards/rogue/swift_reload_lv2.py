"""Swift Reload (Level 2) — Rogue Event. (06161)
快速。只能在你的回合中打出。
选择你控制的一张子弹标记数量少于其"使用(X)"中的X的[[枪械]]支援卡。在该
支援卡上放置子弹，直到其子弹等于其"使用(X)"中的X。

简化说明：
- 目标自动选择：你装备区第一张弹药未满的枪械（按 play_area 顺序）；可用
  ctx.extra["target_instance_id"] 显式指定（官方为玩家选择）。
- "只能在你的回合中打出"的时机校验由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SwiftReload(CardImplementation):
    card_id = "swift_reload_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def reload_firearm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_id = ctx.extra.get("target_instance_id")
        if target_id is None:
            target_id = self._first_reloadable(ctx, inv)
        if target_id is None:
            return
        if not self._is_reloadable(ctx, inv, target_id):
            return

        inst = ctx.game_state.get_card_instance(target_id)
        cd = ctx.game_state.get_card_data(inst.card_id)
        full = (cd.uses or {}).get("ammo", 0)
        added = full - inst.uses.get("ammo", 0)
        inst.uses["ammo"] = full
        ctx.extra["swift_reload_target"] = target_id
        ctx.extra["swift_reload_added"] = added
        ctx.game_state.log_effect(
            f"🔋 快速装填：【{ctx.game_state.card_name(inst.card_id)}】装填{added}发弹药")

    @staticmethod
    def _is_reloadable(ctx, inv, instance_id: str) -> bool:
        """你控制的、弹药少于使用(X)的枪械。"""
        if instance_id not in inv.play_area:
            return False
        inst = ctx.game_state.get_card_instance(instance_id)
        if inst is None:
            return False
        cd = ctx.game_state.get_card_data(inst.card_id)
        if cd is None or "firearm" not in (cd.traits or []):
            return False
        full = (cd.uses or {}).get("ammo")
        if full is None:
            return False
        return inst.uses.get("ammo", 0) < full

    @classmethod
    def _first_reloadable(cls, ctx, inv) -> str | None:
        for iid in inv.play_area:
            if cls._is_reloadable(ctx, inv, iid):
                return iid
        return None
