"""Riot Whistle (Level 0) — Guardian Asset, Accessory slot. (07108)
在你的回合中你可以进行一次额外的行动，该行动只能用于<b>交战</b>。

简化说明：
- 额外行动在你的回合开始时发放（与 leo_de_luca 同一模式）。
- "只能用于交战"的限制由会话层校验（引擎行动系统不区分行动来源，
  列为会话缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class RiotWhistle(CardImplementation):
    card_id = "riot_whistle_lv0"

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def grant_action(self, ctx):
        """回合开始时（在引擎发放3行动之后）给装备者 +1 行动。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            inv.actions_remaining += 1
            ctx.game_state.log_effect("📣 警哨：本回合获得1个额外行动（限交战）")
