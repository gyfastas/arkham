"""Reliable (Level 1) — Guardian Event. (04020)
快速。只能在你的回合中打出。叠加到你控制的一张[[道具]]支援卡。
结算被叠加的支援卡上的触发能力时，你每项技能+1。

简化说明：
- 叠加目标经 ctx.extra["attach_to"] 指定，缺省自动选择你装备区第一张
  带 Item 特征的支援卡；叠加关系记录在 scenario.vars["reliable_attachments"]。
- "触发能力"以检定来源判定：检定的 ctx.source 为被叠加支援卡的实例时，
  视为你正在结算其触发能力，+1 技能值（任意技能）。
- 引擎缺口：事件实现实例在 ROUND_ENDS 被自动注销（engine/actions.py
  _play_event 的清理），永久叠加效果跨轮持续需要引擎支持，见报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_VAR = "reliable_attachments"


class Reliable(CardImplementation):
    card_id = "reliable_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach(self, ctx):
        """打出后：叠加到你控制的一张道具支援卡。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = ctx.extra.get("attach_to")
        if target_iid is None:
            target_iid = self._first_item_asset(ctx.game_state, inv)
        if target_iid is None or target_iid not in inv.play_area:
            ctx.extra["reliable_fizzle"] = True
            return
        target = ctx.game_state.get_card_instance(target_iid)
        data = ctx.game_state.get_card_data(target.card_id) if target else None
        if target is None or data is None or "item" not in (data.traits or []):
            ctx.extra["reliable_fizzle"] = True
            return

        attachments = ctx.game_state.scenario.vars.setdefault(_VAR, {})
        attachments[target_iid] = inv.investigator_id
        self._attached = target_iid
        ctx.extra["reliable_attached"] = target_iid
        ctx.game_state.log_effect(
            f"🔧 值得信赖：叠加到【{ctx.game_state.card_name(target.card_id)}】")

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: str | None = None

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def boost(self, ctx):
        """结算被叠加支援卡的触发能力（检定来源为被叠加卡）时：+1技能值。"""
        attached = self._attached
        if attached is None:
            # 实例重建（如跨轮会话恢复）时从 vars 找回叠加关系
            attachments = ctx.game_state.scenario.vars.get(_VAR, {})
            attached = next(
                (iid for iid, owner in attachments.items()
                 if owner == ctx.investigator_id),
                None,
            )
        if attached is None or ctx.source != attached:
            return
        ctx.modify_amount(1, "reliable_boost")

    @staticmethod
    def _first_item_asset(game_state, inv) -> str | None:
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            data = game_state.get_card_data(inst.card_id) if inst else None
            if data is not None and "item" in (data.traits or []):
                return iid
        return None
