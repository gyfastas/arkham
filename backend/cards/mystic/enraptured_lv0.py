"""Enraptured (Level 0) — Mystic Skill. (04157)
如果调查中的这次技能检定成功，在你控制的1张支援卡上放置1充能或1秘密。

简化说明：
- "调查中"的判定：投入的临时实例在 ST.2 才注册，看不到
  INVESTIGATE_ACTION_INITIATED；以"智力检定且无武器/来源卡"
  （source is None）近似一次调查（引擎无行动类型通道——引擎缺口）。
- 放置目标自动选择：你控制的第一张带充能/秘密的支援卡（无选择 UI）；
  已有秘密的支援放秘密，否则放充能。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Enraptured(CardImplementation):
    card_id = "enraptured_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def place_charge_or_secret(self, ctx):
        """调查检定成功：在你控制的1张支援卡上放置1充能或1秘密。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.INTELLECT or ctx.source is not None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None:
                continue
            if "secrets" in ci.uses:
                ci.uses["secrets"] += 1
                ctx.extra["enraptured_placed"] = {"target": iid, "kind": "secrets"}
                ctx.game_state.log_effect(
                    f"🎶 如痴如醉：【{ctx.game_state.card_name(ci.card_id)}】+1秘密")
                return
            if "charges" in ci.uses:
                ci.uses["charges"] += 1
                ctx.extra["enraptured_placed"] = {"target": iid, "kind": "charges"}
                ctx.game_state.log_effect(
                    f"🎶 如痴如醉：【{ctx.game_state.card_name(ci.card_id)}】+1充能")
                return
