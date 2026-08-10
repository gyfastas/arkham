"""Eucatastrophe (Level 3) — Survivor Event.
Fast. Play when you reveal a chaos token that would reduce your skill value to 0
during a skill test (including the [auto_fail] token).
Cancel that token and treat it as an [elder_sign] token, instead.

简化说明：
- 从手牌中自动触发：满足打出条件且资源足够时自动打出（官方为玩家选择时机）。
- 数值标记：把标记修正改为远古印记数值（0），技能值不再被降为0。
  远古印记的调查员专属效果不触发（从简）。
- 自动失败标记：引擎在 CHAOS_TOKEN_RESOLVED 发出前已锁定 auto_fail，无清除通道
  （引擎缺口）；近似为在 SKILL_TEST_FAILED 时按"视为远古印记"重算
  基础技能+投入图标+资产加值 与难度比较并翻转 ctx.success（同 lucky 机制）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class Eucatastrophe(CardImplementation):
    card_id = "eucatastrophe_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {investigator_id: (base_skill, committed_icons)} 本次检定的快照
        self._snapshot: dict[str, tuple[int, int]] = {}
        # 自动失败标记已取消、等待按远古印记重算的调查员
        self._auto_fail_saved: set[str] = set()

    def _try_play(self, ctx, inv) -> bool:
        """自动打出（支付费用，手牌→弃牌堆）。资源不足则不触发。"""
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 2) or 2) if cd else 2
        if inv.resources < cost:
            return False
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        return True

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.WHEN)
    def snapshot_skill(self, ctx):
        """记录本次检定的基础技能值与投入图标，供"降为0"判定。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        base = ctx.extra.get("base_skill", 0) or 0
        icons = ctx.extra.get("committed_icons", 0) or 0
        self._snapshot[ctx.investigator_id] = (base, icons)

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def cancel_token(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        base, icons = self._snapshot.get(ctx.investigator_id, (0, 0))

        if ctx.chaos_token == ChaosTokenType.AUTO_FAIL:
            if not self._try_play(ctx, inv):
                return
            # 引擎无法清除 auto_fail：标记后在失败判定时按远古印记重算
            self._auto_fail_saved.add(ctx.investigator_id)
            ctx.extra["eucatastrophe_cancelled"] = "auto_fail"
            ctx.game_state.log_effect(
                "🌅 美满结局：取消自动失败标记，视为远古印记")
            return

        # 数值标记：基础+图标+标记修正 ≤ 0 时技能值将被降为0
        if base + icons + (ctx.amount or 0) > 0:
            return
        if not self._try_play(ctx, inv):
            return
        ctx.modify_amount(-(ctx.amount or 0), "eucatastrophe_elder_sign")
        ctx.extra["eucatastrophe_cancelled"] = getattr(
            ctx.chaos_token, "value", str(ctx.chaos_token))
        ctx.game_state.log_effect(
            "🌅 美满结局：取消混沌标记，视为远古印记（修正归0）")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def save_from_auto_fail(self, ctx):
        """自动失败已被取消：按"视为远古印记"（修正0）重算成败。"""
        if ctx.investigator_id not in self._auto_fail_saved:
            return
        if not ctx.extra.get("auto_fail"):
            return
        base = ctx.extra.get("base_skill", 0) or 0
        icons = ctx.extra.get("committed_icons", 0) or 0
        asset_bonus = ctx.extra.get("asset_bonus", 0) or 0
        recomputed = max(0, base + icons + asset_bonus)
        ctx.success = recomputed >= (ctx.difficulty or 0)
        ctx.extra["eucatastrophe_recomputed"] = recomputed

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._snapshot.pop(ctx.investigator_id, None)
        self._auto_fail_saved.discard(ctx.investigator_id)
