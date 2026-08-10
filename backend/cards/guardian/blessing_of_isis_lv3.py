"""Blessing of Isis (Level 3) — Guardian Asset. (07190)
[反应]当你所在地点的一次技能检定中揭示第二个[bless]标记时，横置伊西斯的祝福：
取消该标记并将其视为[elder_sign]标记。本次检定结束后将这两个标记放回混乱袋。

简化说明：
- 因取消/替换可能不利于当前检定（引擎中远古印记基础修正为+0，祝福为+2），
  本卡实现为"武装后自动触发"：经 activations 声明的 arm 能力（快速）武装后，
  下一次满足条件时自动横置并替换标记；未武装则不触发（保留玩家选择权）。
- "同一次检定揭示第二个祝福标记"：CHAOS_TOKEN_RESOLVED 计数本检定内揭示的
  祝福标记，第二个触发。⚠️ 引擎每次检定只揭示1个标记（吃子弹吧等多标记
  效果不逐一发事件），常规流程下本能力无法自然触发——引擎缺口，见报告。
- "检定结束后放回混乱袋"：引擎抽标记本就不移出袋，天然满足（注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class BlessingOfIsis(CardImplementation):
    card_id = "blessing_of_isis_lv3"
    activations = [{
        "id": "arm",
        "label": "武装：下次同地点检定揭示第2个祝福时自动替换为远古印记",
        "method": "activate_arm",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._bless_count = 0

    def activate_arm(self, game_state, investigator_id: str) -> bool:
        """武装：下一次满足条件时自动触发替换。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        self._armed = True
        game_state.log_effect("☥ 伊西斯的祝福：已武装，揭示第2个祝福标记时触发")
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reset_count(self, ctx):
        self._bless_count = 0

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def convert_second_bless(self, ctx):
        """同一检定揭示的第二个祝福标记：横置本卡，取消并视为远古印记。"""
        if ctx.chaos_token != ChaosTokenType.BLESS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        if inv.location_id != owner.location_id:
            return  # 只统计你所在地点的检定
        self._bless_count += 1
        if self._bless_count < 2 or not self._armed or inst.exhausted:
            return
        inst.exhausted = True
        self._armed = False
        # 取消祝福（+2），视为远古印记（引擎基础修正+0；调查员印记能力
        # 挂在同一事件的更晚优先级，会看到替换后的标记）
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "blessing_of_isis_cancel")
        ctx.chaos_token = ChaosTokenType.ELDER_SIGN
        ctx.extra["blessing_of_isis_converted"] = True
        ctx.game_state.log_effect("☥ 伊西斯的祝福：取消第2个祝福标记，视为远古印记")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._bless_count = 0
