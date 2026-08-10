"""Logical Reasoning (Level 0) — Seeker Event.
仅有至少1条线索时才能打出。
选择你所在地点的1位调查员。该调查员治愈2点恐惧，或丢弃其威胁区中的
1张[[Terror]]卡。

简化说明：
- 目标默认为打出者自己，可用 ctx.extra["target_investigator"] 指定
  （须与打出者同地点）；
- 二选一模式自动判定：威胁区有Terror卡则丢弃之（通常更有利），
  否则治愈2点恐惧；可用 ctx.extra["mode"]="heal"/"terror" 强制指定；
- "仅有至少1条线索才能打出"简化为效果不生效（引擎出牌流程不支持前置条件回滚）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LogicalReasoning(CardImplementation):
    card_id = "logical_reasoning_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def apply_effect(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if inv.clues < 1:
            ctx.extra["logical_reasoning_failed"] = "no_clue"
            ctx.game_state.log_effect("🧠 逻辑推理：打出者没有线索，效果不生效")
            return

        target_id = ctx.extra.get("target_investigator") or inv.investigator_id
        target = ctx.game_state.get_investigator(target_id)
        if target is None or target.location_id != inv.location_id:
            return

        mode = ctx.extra.get("mode")
        terror_iid = self._find_terror(ctx, target)
        if mode not in ("heal", "terror"):
            mode = "terror" if terror_iid is not None else "heal"

        if mode == "terror" and terror_iid is not None:
            inst = ctx.game_state.get_card_instance(terror_iid)
            target.threat_area.remove(terror_iid)
            ctx.game_state.cards_in_play.pop(terror_iid, None)
            target.discard.append(inst.card_id)
            ctx.extra["logical_reasoning_discarded"] = inst.card_id
            ctx.game_state.log_effect(
                f"🧠 逻辑推理：丢弃威胁区中的"
                f"【{ctx.game_state.card_name(inst.card_id)}】"
            )
        else:
            healed = min(2, target.horror)
            target.horror -= healed
            ctx.extra["logical_reasoning_healed"] = healed
            ctx.game_state.log_effect(f"🧠 逻辑推理：治愈{healed}点恐惧")

    @staticmethod
    def _find_terror(ctx, target) -> str | None:
        """目标威胁区中第一张带 Terror 特征的卡的实例id。"""
        for iid in target.threat_area:
            inst = ctx.game_state.get_card_instance(iid)
            if inst is None:
                continue
            cd = ctx.game_state.get_card_data(inst.card_id)
            if cd is not None and "terror" in [t.lower() for t in (cd.traits or [])]:
                return iid
        return None
