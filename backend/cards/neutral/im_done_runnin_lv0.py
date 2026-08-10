""""I'm done runnin'!" (Level 0) — Neutral Event. Rita Young 专属。
快速。仅在你的回合中打出。
准备并交战你所在地点的所有敌人。直到你回合结束，每当你躲避一名敌人时，
你可以对其造成1点伤害，代替横置并脱离交战。（躲避成功的其他效果仍适用。）

简化说明：
- 引擎在躲避成功的 on_success 中先横置/脱离交战再发 ENEMY_EVADED，
  "代替横置与脱离交战"无法拦截（引擎缺口）；实现为躲避成功后自动对该
  敌人造成1点伤害（"可以"简化为自动），敌人仍横置并脱离交战，特此注明。
- 准备并交战：当前地点未交战敌人及同地点其他调查员威胁区中的敌人
  全部准备并移入你的威胁区。
- 回合内持续效果用 impl 实例标记，INVESTIGATOR_TURN_ENDS 时清除。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ImDoneRunnin(CardImplementation):
    card_id = "im_done_runnin_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._active_for: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def ready_and_engage(self, ctx):
        if ctx.extra.get("card_id") != "im_done_runnin_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        location = ctx.game_state.get_location(inv.location_id)
        engaged = 0
        # 当前地点未交战的敌人
        if location is not None:
            for enemy_iid in list(location.enemies):
                location.enemies.remove(enemy_iid)
                inv.threat_area.append(enemy_iid)
                engaged += 1
        # 同地点其他调查员威胁区中的敌人
        for other in ctx.game_state.investigators.values():
            if other.investigator_id == inv.investigator_id:
                continue
            if other.location_id != inv.location_id:
                continue
            for enemy_iid in list(other.threat_area):
                other.threat_area.remove(enemy_iid)
                inv.threat_area.append(enemy_iid)
                engaged += 1
        # 准备所有交战的敌人
        for enemy_iid in inv.threat_area:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                enemy.exhausted = False
        self._active_for = inv.investigator_id
        ctx.game_state.log_effect(
            f"🔥 我受够逃跑了！：准备并交战 {engaged} 名敌人；"
            "本回合躲避改为造成1点伤害"
        )

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def damage_instead(self, ctx):
        """本回合内你躲避敌人后：对其造成1点伤害。"""
        if self._active_for is None or ctx.investigator_id != self._active_for:
            return
        if deal_damage_to_enemy(
            ctx.game_state, self._bus, ctx.enemy_id, 1,
            defeated_by=ctx.investigator_id,
        ):
            ctx.game_state.log_effect("🔥 我受够逃跑了！：躲避造成1点伤害，敌人被击败")
        else:
            ctx.game_state.log_effect("🔥 我受够逃跑了！：躲避造成1点伤害")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.investigator_id == self._active_for:
            self._active_for = None
