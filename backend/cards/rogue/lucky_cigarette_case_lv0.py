"""Lucky Cigarette Case (Level 0) — Rogue Asset. (04107)
[反应]在你技能检定成功且超出难度2点以上后，消耗幸运烟盒：抽1张牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LuckyCigaretteCase(CardImplementation):
    card_id = "lucky_cigarette_case_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def draw_on_big_success(self, ctx):
        """成功超出难度2点以上：消耗本卡，抽1张牌。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            return
        inst.exhausted = True
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["lucky_cigarette_case_draw"] = True
            ctx.game_state.log_effect("🚬 幸运烟盒：成功超2，抽1张牌")
