"""Medical Student (Level 0) — Guardian Asset, Ally slot. (08083)
[反应] 在医学生入场后：治愈你所在地点一位调查员或一张[[盟友]]支援卡的
1点伤害和1点恐惧。

简化说明：
- 治愈目标自动选择：同地点（含控制者）中"伤害+恐惧"最多的调查员，
  其次有需要治愈的盟友；可经 ctx.extra["heal_target"]
  （investigator_id 或盟友 instance_id）指定。
- 伤害与恐惧各治愈1点（不足则有多少治多少）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MedicalStudent(CardImplementation):
    card_id = "medical_student_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def heal_on_enter(self, ctx):
        """入场后：治愈同地点一个目标的1伤害和1恐惧。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target_id = ctx.extra.get("heal_target") or self._auto_target(ctx, inv)
        if target_id is None:
            return

        target_inv = ctx.game_state.get_investigator(target_id)
        if target_inv is not None:
            healed_d = min(1, target_inv.damage)
            healed_h = min(1, target_inv.horror)
            target_inv.damage -= healed_d
            target_inv.horror -= healed_h
        else:
            inst = ctx.game_state.get_card_instance(target_id)
            if inst is None:
                return
            healed_d = min(1, inst.damage)
            healed_h = min(1, inst.horror)
            inst.damage -= healed_d
            inst.horror -= healed_h
        if healed_d or healed_h:
            ctx.extra["medical_student_healed"] = target_id
            ctx.game_state.log_effect(
                f"🩺 医学生：治愈{healed_d}点伤害和{healed_h}点恐惧")

    @staticmethod
    def _auto_target(ctx, inv) -> str | None:
        """自动目标：同地点 伤害+恐惧 最多的调查员，其次有需要的盟友。"""
        investigators = ctx.game_state.get_investigators_at_location(inv.location_id)
        hurt = [i for i in investigators if i.damage + i.horror > 0]
        if hurt:
            return max(hurt, key=lambda i: i.damage + i.horror).investigator_id
        for other in investigators:
            for iid in other.play_area:
                ci = ctx.game_state.get_card_instance(iid)
                cd = ctx.game_state.get_card_data(ci.card_id) if ci else None
                if cd is not None and "ally" in (cd.traits or []) \
                        and ci.damage + ci.horror > 0:
                    return iid
        return None
