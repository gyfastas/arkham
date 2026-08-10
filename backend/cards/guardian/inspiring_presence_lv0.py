"""Inspiring Presence (Level 0) — Guardian Skill. (03228)
如果本次技能检定成功，准备你所在地点的一张盟友支援卡，
并为其治愈1点伤害或1点恐惧。

简化说明：
- 目标与治愈类型自动选择：优先自己控制的盟友中"横置或带伤/恐惧"的第一张
  （同地点其他调查员的盟友亦可）；治愈优先伤害，其次恐惧。
- 同地点没有盟友时不产生效果。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class InspiringPresence(CardImplementation):
    card_id = "inspiring_presence_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def inspire_ally(self, ctx):
        """成功时：准备同地点一张盟友并治愈其1点伤害或恐惧。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 收集同地点盟友（自己控制的优先），挑出横置或有伤/恐惧的第一张
        allies = []
        others = []
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            bucket = allies if other.investigator_id == inv.investigator_id else others
            for iid in other.play_area:
                inst = ctx.game_state.get_card_instance(iid)
                data = ctx.game_state.get_card_data(inst.card_id) if inst else None
                if data is not None and "ally" in (data.traits or []):
                    bucket.append(inst)
        target = next(
            (a for a in allies + others
             if a.exhausted or a.damage > 0 or a.horror > 0),
            None,
        )
        if target is None:
            return

        target.exhausted = False
        healed = None
        if target.damage > 0:
            target.damage -= 1
            healed = "damage"
        elif target.horror > 0:
            target.horror -= 1
            healed = "horror"
        ctx.extra["inspiring_presence_target"] = target.instance_id
        ctx.extra["inspiring_presence_healed"] = healed
        ctx.game_state.log_effect(
            f"🚩 激励存在：准备【{ctx.game_state.card_name(target.card_id)}】"
            + ("并治愈1点" + ("伤害" if healed == "damage" else "恐惧") if healed else ""))
