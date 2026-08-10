"""Borrowed Time (Level 3) — Rogue Asset, Arcane slot. (04308)
卓越。
[行动]：在时间借取上放置1资源，视为一声滴答（最多3声滴答）。此行动不会
引起趁乱攻击。
强制 - 在你回合开始时：移除时间借取上所有的滴答。你本回合可以额外进行
等量的行动。

简化说明：
- 滴答计数存放在卡牌实例 uses["clicks"]（数据无 uses 字段，运行时新增键）。
- "此行动不会引起趁乱攻击"：引擎的 ACTIVATE 行动 AoO 由会话层统一结算，
  卡牌代码无法豁免单个启动能力（引擎缺口，已在报告中列出）。
- "卓越"（每牌组限1）为牌组构建规则，由会话层负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_MAX_CLICKS = 3


class BorrowedTime(CardImplementation):
    card_id = "borrowed_time_lv3"
    activations = [{
        "id": "add_click",
        "label": "放1资源为1声滴答（至多3；下回合开始换成额外行动）",
        "method": "add_click",
        "actions": 1,
    }]

    def add_click(self, game_state, investigator_id: str) -> bool:
        """[行动]：花1资源在卡上放1声滴答（最多3声）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if inv.resources < 1:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        clicks = inst.uses.get("clicks", 0)
        if clicks >= _MAX_CLICKS:
            return False
        inv.resources -= 1
        inst.uses["clicks"] = clicks + 1
        game_state.log_effect(
            f"⏳ 时间借取：放置1声滴答（当前{clicks + 1}声）")
        return True

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def convert_clicks(self, ctx):
        """强制 - 你回合开始时：移除所有滴答，换成等量额外行动。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        clicks = inst.uses.get("clicks", 0)
        if clicks <= 0:
            return
        inst.uses["clicks"] = 0
        inv.actions_remaining += clicks
        ctx.game_state.log_effect(
            f"⏳ 时间借取：移除{clicks}声滴答，本回合额外{clicks}个行动")
        ctx.extra["borrowed_time_actions"] = clicks
