"""In the Shadows (Level 0) — Neutral Event. Trish Scarborough 专属。
快速。在你的回合开始后打出。
脱离所有与你交战的敌人。直到回合结束，敌人不能与你交战，
你也不能对敌人造成伤害。

简化说明：
- "敌人不能与你交战"：引擎 ENEMY_ENGAGED 不支持取消，实现为交战发生后
  立即把敌人移回你所在地点的未交战列表（等效结果）。
- "你不能对敌人造成伤害"：DAMAGE_DEALT 时把伤害修正为0。
- 效果按轮次生效（回合结束在轮次内），ROUND_ENDS 时清除（事件 impl 届时
  也会被引擎自动注销）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class InTheShadows(CardImplementation):
    card_id = "in_the_shadows_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._active_inv: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def disengage_all(self, ctx):
        if ctx.extra.get("card_id") != "in_the_shadows_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        count = 0
        for enemy_iid in list(inv.threat_area):
            inv.threat_area.remove(enemy_iid)
            if location is not None and enemy_iid not in location.enemies:
                location.enemies.append(enemy_iid)
            count += 1
        self._active_inv = inv.investigator_id
        ctx.game_state.log_effect(
            f"🌫️ 暗影之中：脱离 {count} 名敌人；本轮敌人不能与你交战，"
            "你不能对敌人造成伤害"
        )

    @on_event(GameEvent.ENEMY_ENGAGED, priority=TimingPriority.AFTER)
    def prevent_engagement(self, ctx):
        if self._active_inv is None or ctx.investigator_id != self._active_inv:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or ctx.enemy_id not in inv.threat_area:
            return
        inv.threat_area.remove(ctx.enemy_id)
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and ctx.enemy_id not in location.enemies:
            location.enemies.append(ctx.enemy_id)
        ctx.game_state.log_effect("🌫️ 暗影之中：敌人无法与你交战")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def prevent_damage(self, ctx):
        if self._active_inv is None or ctx.investigator_id != self._active_inv:
            return
        if (ctx.amount or 0) > 0:
            ctx.modify_amount(-ctx.amount, "in_the_shadows_no_damage")
            ctx.game_state.log_effect("🌫️ 暗影之中：你不能对敌人造成伤害")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._active_inv = None
