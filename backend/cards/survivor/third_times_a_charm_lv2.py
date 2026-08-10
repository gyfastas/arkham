"""Third Time's a Charm (Level 2) — Survivor Event. (07161)
快速。在你所在地点技能检定开始时打出。
这次检定中两次，在调查员抽出混乱标记时，可以将其取消，返回混乱袋，并抽出
一个新的混乱标记。

简化说明：
- 从手牌中自动打出：技能检定开始时，若执行检定的调查员手牌中有本卡且
  资源足够，自动支付1资源打出（官方为"你所在地点"的任一检定由玩家选择
  打出，此处同 lucky/eucatastrophe 的自动打出模式，限定为持有者自己的
  检定）；经会话层正常 PLAY 打出（CARD_PLAYED）时同样武装。
- "可以取消"自动执行为：仅当标记为 [auto_fail] 或数值修正为负时取消重抽
  （每次检定最多2次；官方为玩家自选，良性标记不会想取消）。
- 引擎在 _st3 已把标记写入检定结果，CHAOS_TOKEN_REVEALED 阶段改不动结果；
  取消在 CHAOS_TOKEN_RESOLVED（WHEN）结算：从袋中另抽一枚标记，改写修正值
  与 ctx.chaos_token，并视新旧标记经 force_auto_fail/cancel_auto_fail 通道
  修正自动失败状态（同 seal_of_the_elder_sign 的替换口径）。结果对象上的
  原始标记仅影响 UI 展示（引擎缺口，见报告）。
- 引擎抽袋不移除标记，"返回混乱袋"天然成立；新抽标记自袋中取得。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class ThirdTimesACharm(CardImplementation):
    card_id = "third_times_a_charm_lv2"
    persistent_in_hand = True  # 在手牌中持续监听检定开始窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._remaining = 0

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / draw_hooks 接线）。"""
        self._chaos_bag = chaos_bag

    def _arm(self) -> None:
        self._remaining = 2

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def auto_play(self, ctx):
        """你所在地点的技能检定开始时：自动从手牌打出。"""
        if self._remaining:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._arm()
        ctx.extra["third_times_a_charm_played"] = True
        ctx.game_state.log_effect("🍀 事不过三：打出，本次检定可两次取消重抽标记")

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def on_played(self, ctx):
        """经会话层正常打出时同样武装。"""
        if ctx.extra.get("card_id") == self.card_id:
            self._arm()

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def reroll_token(self, ctx):
        """取消不利标记并另抽一枚（每次检定最多2次；新标记仍不利则继续）。"""
        if self._remaining <= 0:
            return
        bag = getattr(self, "_chaos_bag", None)
        if bag is None:
            return
        while self._remaining > 0 and bag.tokens:
            token = ctx.chaos_token
            is_bad = (
                token == ChaosTokenType.AUTO_FAIL
                or (CHAOS_TOKEN_VALUES.get(token) or 0) < 0
            )
            if not is_bad:
                break

            self._remaining -= 1
            new_token = bag.draw()
            new_modifier = CHAOS_TOKEN_VALUES.get(new_token) or 0
            # 改写修正值（符号标记按0处理，同引擎默认）
            delta = new_modifier - (ctx.amount or 0)
            if delta:
                ctx.modify_amount(delta, "third_times_a_charm_reroll")
            if new_token == ChaosTokenType.AUTO_FAIL:
                ctx.extra["force_auto_fail"] = True
                ctx.extra.pop("cancel_auto_fail", None)
            elif token == ChaosTokenType.AUTO_FAIL:
                ctx.extra["cancel_auto_fail"] = True
                ctx.extra.pop("force_auto_fail", None)
            ctx.chaos_token = new_token
            ctx.extra["third_times_a_charm_rerolled"] = getattr(
                new_token, "value", str(new_token))
            ctx.game_state.log_effect(
                f"🍀 事不过三：取消 {getattr(token, 'value', token)}，"
                f"重抽为 {getattr(new_token, 'value', new_token)}"
                f"（剩{self._remaining}次）")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._remaining = 0
