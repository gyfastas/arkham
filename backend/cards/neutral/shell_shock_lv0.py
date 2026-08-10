"""Shell Shock (Level 0) — Neutral Treachery, Signature Weakness (Mark Harrigan).
显现：你身上每有2点伤害，受到1点恐惧。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ShellShock(CardImplementation):
    card_id = "shell_shock_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "shell_shock_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "shell_shock_lv0" in inv.hand:
            inv.hand.remove("shell_shock_lv0")

        horror_taken = inv.damage // 2
        inv.horror += horror_taken  # 直接恐惧（不分配）
        inv.discard.append("shell_shock_lv0")
        ctx.extra["shell_shock_horror"] = horror_taken
        if horror_taken:
            ctx.game_state.log_effect(
                f"💥 炮弹休克：身上有{inv.damage}点伤害，受到{horror_taken}点恐惧"
            )
