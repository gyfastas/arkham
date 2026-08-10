"""You Handle This One! (Level 0) — Rogue Event.
快速。在你抽到一张非危难遭遇卡后、结算其效果前打出。
选择另一位调查员。该调查员被视为抽到了该遭遇卡。获得1资源。

简化说明：
- 遭遇卡重定向需要多人局与目标选择 UI，暂未实现（待做：监听 ENCOUNTER_CARD_DRAWN，非 peril 时给玩家选择另一调查员并设 ctx.extra["redirect_to"]）；
  单人局该效果无意义，当前仅结算"获得1资源"。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class YouHandleThisOne(CardImplementation):
    card_id = "you_handle_this_one_lv0"


    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.AFTER,
    )
    def gain_resource(self, ctx):
        """Gain 1 resource when this card is played."""
        if ctx.extra.get("card_id") != "you_handle_this_one_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv:
            inv.resources += 1
