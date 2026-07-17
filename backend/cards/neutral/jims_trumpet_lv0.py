"""吉姆的小号（Jim's Trumpet，Level 0）— 吉姆·卡尔弗专属支援卡。
[反应]在技能检定期间抽出[骷髅]标记时，横置吉姆的小号：
治愈你所在地点或连接地点一名调查员的1点恐惧。

简化说明：固定治愈小号控制者本人，不支持选择同地点/连接地点的
其他调查员（目标选择需要UI交互）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class JimsTrumpet(CardImplementation):
    card_id = "jims_trumpet_lv0"

    @on_event(
        GameEvent.CHAOS_TOKEN_REVEALED,
        priority=TimingPriority.REACTION,
    )
    def heal_on_skull(self, ctx):
        """When a skull token is revealed during a skill test, exhaust to
        heal 1 horror from the controller."""
        if ctx.chaos_token != ChaosTokenType.SKULL:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.exhausted:
            return
        card.exhausted = True
        inv.horror = max(0, inv.horror - 1)
