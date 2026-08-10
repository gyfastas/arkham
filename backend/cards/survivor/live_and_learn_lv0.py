"""Live and Learn (Level 0) — Survivor Event. (04280 批次)
Fast. Play after a skill test you failed ends (after resolving all effects
from the failed test).
Attempt that test again. You get +2 skill value for this test.

简化说明：
- 从手牌中自动触发（persistent_in_hand）：你检定失败时若手牌中有本卡，
  自动打出（0费）。
- 官方为重新检定（重抽混沌标记）；引擎的检定回调（on_success/on_failure）
  卡牌代码访问不到，近似为同 Lucky 的"败局翻转"：本次检定 +2 技能值，
  差值≤2 时翻为成功（不重抽标记）。差值>2 时仍失败（卡已消耗）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LiveAndLearn(CardImplementation):
    card_id = "live_and_learn_lv0"
    persistent_in_hand = True  # 在手牌中持续监听失败窗口

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def retry_with_bonus(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        # 自动打出（0费；官方为玩家自行选择打出时机）
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # +2 技能值重试：差值≤2 时翻转结果，否则仍然失败
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin <= 2:
            ctx.success = True
            ctx.extra["live_and_learn_turned_success"] = True
            ctx.game_state.log_effect(
                "📚 吃一堑长一智：+2技能值重试，检定失败转为成功")
        else:
            ctx.game_state.log_effect(
                f"📚 吃一堑长一智：+2技能值重试（差{margin}点，仍失败）")
