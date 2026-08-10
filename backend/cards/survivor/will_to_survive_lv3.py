"""Will to Survive (Level 3) — Survivor Event.
Fast. Play only during your turn.
Until the end of your turn, do not reveal chaos tokens for any skill tests you perform.

简化说明：
- 引擎无"跳过揭示混沌标记"通道：近似为在 CHAOS_TOKEN_RESOLVED 把标记数值
  修正归零；自动失败标记（引擎在事件前锁定 auto_fail，无清除通道）则在
  SKILL_TEST_FAILED 按"未揭示标记"（基础+图标+资产加值 对 难度）重算翻转。
- 剧本参考卡的符号标记效果（skull/cultist 等按标记类型触发的效果）仍可能
  生效——引擎缺口，见修复报告。
- "只能在你的回合打出"由出牌时机约束（引擎/UI），实现内不重复校验。
- 效果在持有者自己的回合结束时过期（官方：直到你的回合结束）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WillToSurvive(CardImplementation):
    card_id = "will_to_survive_lv3"

    def _effect_holder(self, ctx):
        """返回持有本效果的调查员（仅当事件属于其本人时）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return None
        if not getattr(inv, "active_effects", {}).get("will_to_survive"):
            return None
        return inv

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def activate_effect(self, ctx):
        if ctx.extra.get("card_id") != "will_to_survive_lv3":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects["will_to_survive"] = True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def neutralize_token(self, ctx):
        """不揭示混沌标记：标记数值修正归零。"""
        if self._effect_holder(ctx) is None:
            return
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "will_to_survive_no_token")
            ctx.extra["will_to_survive_token_skipped"] = True

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def ignore_auto_fail(self, ctx):
        """不揭示标记即无自动失败：按未揭示标记重算成败。"""
        if self._effect_holder(ctx) is None:
            return
        if not ctx.extra.get("auto_fail"):
            return
        base = ctx.extra.get("base_skill", 0) or 0
        icons = ctx.extra.get("committed_icons", 0) or 0
        asset_bonus = ctx.extra.get("asset_bonus", 0) or 0
        recomputed = max(0, base + icons + asset_bonus)
        ctx.success = recomputed >= (ctx.difficulty or 0)
        ctx.extra["will_to_survive_recomputed"] = recomputed

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """直到你的回合结束：仅清除回合结束者本人持有的效果。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if getattr(inv, "active_effects", None):
            inv.active_effects.pop("will_to_survive", None)
