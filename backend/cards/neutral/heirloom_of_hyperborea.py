"""许珀耳玻瑞亚传家宝（Heirloom of Hyperborea）— 阿格尼丝·贝克专属支援卡，饰品。
[反应]在你打出一张法术(Spell)牌后：抽1张牌。

简化说明：JSON 未限制每轮次数，故不设限。事件类法术牌通过 CARD_PLAYED
触发，支援类法术牌入场通过 CARD_ENTERS_PLAY 触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class HeirloomOfHyperborea(CardImplementation):
    card_id = "heirloom_of_hyperborea"

    @on_event(
        GameEvent.CARD_ENTERS_PLAY,
        priority=TimingPriority.REACTION,
    )
    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.REACTION,
    )
    def draw_on_spell(self, ctx):
        """After the controller plays a Spell card, draw 1 card."""
        card_id = ctx.extra.get("card_id")
        if not card_id or card_id == "heirloom_of_hyperborea":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        card_data = ctx.game_state.get_card_data(card_id)
        if card_data is None or "spell" not in (card_data.traits or []):
            return
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
