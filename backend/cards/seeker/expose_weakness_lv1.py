"""Expose Weakness (Level 1) — Seeker Event.
选择一个在你地点的敌人。查看该敌人的牌面文字。发现1条线索（如果该敌人是精英，则改为发现2条线索）。

简化说明：
- 目标默认为你所在地点的第一个敌人（交战优先），可用 ctx.extra["enemy_instance_id"] 指定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ExposeWeakness(CardImplementation):
    card_id = "expose_weakness_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def discover_clues(self, ctx):
        if ctx.extra.get("card_id") != "expose_weakness_lv1":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        enemy = None
        enemy_iid = ctx.extra.get("enemy_instance_id")
        if enemy_iid:
            enemy = ctx.game_state.get_card_instance(enemy_iid)
        if enemy is None:
            candidates = list(inv.threat_area)
            loc = ctx.game_state.get_location(inv.location_id)
            if loc is not None:
                candidates += list(loc.enemies)
            for iid in candidates:
                inst = ctx.game_state.get_card_instance(iid)
                if inst is not None:
                    enemy = inst
                    break
        if enemy is None:
            return

        cd = ctx.game_state.get_card_data(enemy.card_id)
        is_elite = bool(cd and "elite" in (cd.traits or []))
        clues = 2 if is_elite else 1
        inv.clues += clues
        ctx.extra["expose_weakness_clues"] = clues
