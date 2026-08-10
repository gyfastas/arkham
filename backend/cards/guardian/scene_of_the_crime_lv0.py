"""Scene of the Crime (Level 0) — Guardian Event. (04103)
只可作为你的第一个行动打出。发现你所在地点的1个线索(如果该地点有敌人，
改为发现2个线索)。此行动不会引起趁乱攻击。

简化说明：
- "第一个行动"：引擎只跟踪 actions_remaining（回合开始重置为3），本卡以
  actions_remaining >= 3 近似判定（与 mano_a_mano 同一约定；完整校验由
  会话层负责）。不满足时效果不结算（注明）。
- "该地点有敌人"：地点上的未交战敌人或同地点调查员威胁区中的敌人均算。
- 不引起趁乱攻击：CARD_PLAYED 先于 AoO 发出，武装一次性豁免标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SceneOfTheCrime(CardImplementation):
    card_id = "scene_of_the_crime_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._aoo_free: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discover(self, ctx):
        """第一个行动：发现1线索（地点有敌人则2条）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.actions_remaining < 3:
            # 简化：满行动视作本回合第一个行动（见 docstring）
            ctx.extra["scene_of_the_crime_fizzle"] = True
            ctx.game_state.log_effect("🔍 犯罪现场：不是本回合第一个行动，效果不结算")
            return

        location = ctx.game_state.get_location(inv.location_id)
        if location is None:
            return

        enemy_present = bool(location.enemies) or any(
            other.threat_area
            for other in ctx.game_state.get_investigators_at_location(inv.location_id)
        )
        amount = 2 if enemy_present else 1
        discovered = 0
        for _ in range(amount):
            if location.clues > 0:
                location.clues -= 1
                inv.clues += 1
                discovered += 1

        ctx.extra["scene_of_the_crime_discovered"] = discovered
        ctx.game_state.log_effect(f"🔍 犯罪现场：发现{discovered}条线索")

        # 此行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
