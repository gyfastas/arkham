"""Jury-Rig (Level 0) — Survivor Event. (08074)
Uses (3 durability).
Attach to an [Item] asset controlled by an investigator at your location.
[fast] During a skill test on attached asset, spend 1 durability: You get
+2 skill value for this test.

简化说明：
- 引擎中事件结算后进弃牌堆、无"叠加在场"状态：附加关系登记在
  scenario.vars["jury_rig"]（{asset, durability, owner}，同 hiding_spot
  的 vars 标记模式）。
- 目标选择自动化：默认你所在地点由你控制的第一张道具支援，可经
  ctx.extra["asset_instance_id"] 指定。
- 代付为公开方法 spend()（花费1耐久，武装下一次被附加资产的检定 +2，
  可叠加）；事件实现实例在 ROUND_ENDS 被引擎清理，跨轮持续为引擎缺口
  （同 hiding_spot，见报告）。
- 数据 uses 键为 "durabilitys"（复数化数据 artifact），耐久数以卡面3为准。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_DURABILITY = 3


class JuryRig(CardImplementation):
    card_id = "jury_rig_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0  # 已花费耐久、待生效的 +2 次数

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_item(self, ctx):
        """打出时：叠加到你所在地点的一张道具支援。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_iid = self._choose_target(ctx, inv)
        if target_iid is None:
            ctx.extra["jury_rig_fizzled"] = True
            return
        ctx.game_state.scenario.vars["jury_rig"] = {
            "asset": target_iid,
            "durability": _DURABILITY,
            "owner": inv.investigator_id,
        }
        ctx.extra["jury_rig_attached"] = target_iid
        target = ctx.game_state.get_card_instance(target_iid)
        ctx.game_state.log_effect(
            f"🔧 应急改装：叠加到【{ctx.game_state.card_name(target.card_id)}】"
            f"（3耐久）" if target else "🔧 应急改装：已叠加")

    def _choose_target(self, ctx, inv) -> str | None:
        explicit = ctx.extra.get("asset_instance_id")
        if explicit:
            return explicit
        # 自动选你所在地点的第一张道具支援（优先自己控制的）
        candidates = [
            other for other in ctx.game_state.investigators.values()
            if other.location_id == inv.location_id
        ]
        candidates.sort(key=lambda o: o.investigator_id != inv.investigator_id)
        for other in candidates:
            for iid in other.play_area:
                ci = ctx.game_state.get_card_instance(iid)
                cd = ctx.game_state.get_card_data(ci.card_id) if ci else None
                if cd is not None and cd.type == CardType.ASSET \
                        and "item" in (cd.traits or []):
                    return iid
        return None

    def spend(self, game_state, investigator_id: str) -> bool:
        """[fast] 花费1耐久：下一次被附加资产的检定 +2 技能值（可叠加）。"""
        state = game_state.scenario.vars.get("jury_rig")
        if not state or state.get("durability", 0) < 1:
            return False
        state["durability"] -= 1
        self._armed += 1
        game_state.log_effect("🔧 应急改装：花费1耐久，本次检定+2")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """被附加资产发起的检定：每次花费 +2。"""
        if not self._armed:
            return
        state = ctx.game_state.scenario.vars.get("jury_rig")
        if not state or ctx.source != state.get("asset"):
            return
        ctx.modify_amount(2 * self._armed, "jury_rig_boost")
        self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0
