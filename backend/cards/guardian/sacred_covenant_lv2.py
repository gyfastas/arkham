"""Sacred Covenant (Level 2) — Guardian Asset. (07110)
永久。每副牌组限制1张[[圣约]]。
[reaction]在任意地点的调查员执行技能检定的"抽出混乱标记"步骤后，
消耗庄严圣约：将这次检定中抽出的任意数量的[bless]标记返回混乱袋，
这次检定忽略其修正值。

简化说明：
- 引擎抽标记不从袋中移除（chaos_bag.draw 为纯随机取样），"返回混乱袋"
  为无操作；实际效果为忽略祝福标记的+2修正（修正值归零）。
- 是否使用由玩家决定（忽略+2通常不利，故不自动触发）：会话层在标记揭示后
  调用 arm() 武装，随后的 CHAOS_TOKEN_RESOLVED 消耗本卡并将祝福修正归零。
- 引擎每次检定只揭示1个标记，"任意数量"简化为对揭示的每个祝福标记各生效
  一次（本卡横置后不再生效）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SacredCovenant(CardImplementation):
    card_id = "sacred_covenant_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def arm(self, game_state, investigator_id: str) -> bool:
        """[reaction] 武装：本次检定揭示的祝福标记修正将被忽略。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        self._armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def ignore_bless(self, ctx):
        """武装后：忽略本次检定揭示的祝福标记修正值，消耗本卡。"""
        if not self._armed or ctx.chaos_token != ChaosTokenType.BLESS:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            self._armed = False
            return
        inst.exhausted = True
        self._armed = False
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "sacred_covenant_ignore_bless")
        ctx.extra["sacred_covenant_returned"] = True
        ctx.game_state.log_effect(
            "🕊️ 庄严圣约：消耗，祝福标记返回混乱袋并忽略其修正值")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
