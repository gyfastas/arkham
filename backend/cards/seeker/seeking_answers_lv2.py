"""Seeking Answers (Level 2) — Seeker Event.
快速。在你成功调查超过难度2点或以上后打出。发现并消耗该地点的一个线索，发现一个相邻地点的线索。

简化说明：
- 从手牌中自动触发：调查成功超过难度2点时自动打出，
  从所在地点与第一个有线索的相邻地点各发现1个线索。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SeekingAnswersLv2(CardImplementation):
    card_id = "seeking_answers_lv2"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def discover_two_clues(self, ctx):
        if ctx.skill_type != Skill.INTELLECT:
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) < 2:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or "seeking_answers_lv2" not in inv.hand:
            return

        # 自动打出
        cost = 1
        cd = ctx.game_state.get_card_data("seeking_answers_lv2")
        if cd is not None and getattr(cd, "cost", None) is not None:
            cost = cd.cost
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove("seeking_answers_lv2")
        inv.discard.append("seeking_answers_lv2")

        # 所在地点发现1个线索
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1

        # 相邻地点发现1个线索
        if loc is not None:
            for conn_id in getattr(loc, "connections", []) or []:
                conn = ctx.game_state.get_location(conn_id)
                if conn is not None and conn.clues > 0:
                    conn.clues -= 1
                    inv.clues += 1
                    ctx.extra["seeking_answers_connected"] = conn_id
                    break

        ctx.extra["seeking_answers_played"] = True
