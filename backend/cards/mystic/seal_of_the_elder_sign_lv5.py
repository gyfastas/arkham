"""Seal of the Elder Sign (Level 5) — Mystic Skill. (03312)
本次检定不要从混乱袋中揭示混乱标记。将本次检定揭示的混乱标记视为[elder_sign]。
本次检定结束时，从游戏中移除远古印记封印。

简化说明：
- 标记替换：CHAOS_TOKEN_RESOLVED 时将标记改写为远古印记、清零原标记修正、
  并取消自动失败（引擎 _st4 在事件前已按原标记设置 auto_fail，经
  ctx.extra["cancel_auto_fail"] 通道撤销，与 eucatastrophe 同通道）。
- 已知限制（引擎缺口）：调查员的远古印记能力（如阿格尼丝）挂在同一事件同一
  优先级且注册更早，先于本替换触发，故调查员专属的印记加成不会重复结算；
  标记修正按基础远古印记（+0）处理。
- "不从袋中揭示"无法阻止引擎抽袋（标记在 _st3 已抽出），以"视为远古印记"
  等效结算。
- 移出游戏记录在 scenario.vars["removed_from_game"]（引擎无独立移除区）。
  技能检定结束（ST.8）时投入的牌已入弃牌堆，从弃牌堆移除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SealOfTheElderSign(CardImplementation):
    card_id = "seal_of_the_elder_sign_lv5"
    # 投入本卡即必须结算效果（非可选），费用为0
    commit_effect_cost = 0
    commit_effect_label = "将本次检定的标记视为远古印记"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def treat_as_elder_sign(self, ctx):
        """将本次检定揭示的标记视为远古印记。"""
        if ctx.chaos_token == ChaosTokenType.ELDER_SIGN:
            return
        # 清零原标记修正（远古印记基础修正为0，调查员能力另行结算）
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "seal_of_the_elder_sign")
        ctx.chaos_token = ChaosTokenType.ELDER_SIGN
        ctx.extra["cancel_auto_fail"] = True
        ctx.extra["seal_of_the_elder_sign"] = True
        ctx.game_state.log_effect("✡ 远古印记封印：本次标记视为远古印记")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def remove_from_game(self, ctx):
        """检定结束时：从游戏中移除本卡。"""
        for inv in ctx.game_state.investigators.values():
            removed = False
            for zone in (inv.discard, inv.hand):
                while self.card_id in zone:
                    zone.remove(self.card_id)
                    removed = True
            if removed:
                ctx.game_state.scenario.vars.setdefault(
                    "removed_from_game", []).append(self.card_id)
                return
