"""Daisy Walker — Seeker Investigator.
能力：每回合可执行1个额外行动，只能用于启动典籍(Tome)能力。
远古印记：+0，成功时每控制1个典籍抽1张牌。

说明：
- 额外行动通过 tome_actions_remaining 授予（仅限典籍能力，由
  TOME_ACTIVATE / 会话层 _spend_activate_action 消费），不再同时
  增加普通行动数（此前 +1 actions_remaining 会导致实际5行动）；
- 远古印记的典籍计数在 CHAOS_TOKEN_RESOLVED(ST.4) 记录到调查员状态，
  SKILL_TEST_SUCCESSFUL(ST.6) 跨事件读取（此前存 ctx.extra 后用
  getattr(ctx,'_extra') 读取——该属性不存在，永远抽不到牌）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_TOMES = "daisy_elder_sign_tomes"


class DaisyWalker(CardImplementation):
    card_id = "daisy_walker"

    def _get_daisy(self, game_state, investigator_id):
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "daisy_walker":
            return None
        return inv

    @on_event(
        GameEvent.INVESTIGATION_PHASE_BEGINS,
        priority=TimingPriority.WHEN,
    )
    def grant_tome_action(self, ctx):
        """每回合授予1个仅限典籍能力的额外行动（不增加普通行动数）。"""
        inv = self._get_daisy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        # Grant 1 tome-specific action each investigation phase (resets, does
        # not stack — official: the extra action is granted each turn anew)
        inv.tome_actions_remaining = 1

    @on_event(
        GameEvent.CHAOS_TOKEN_RESOLVED,
        priority=TimingPriority.WHEN,
    )
    def elder_sign_effect(self, ctx):
        """远古印记：+0。成功时抽牌数=控制典籍数（计数先存到调查员状态）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_daisy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        # +0 modifier (already default)
        tome_count = 0
        for inst_id in inv.play_area:
            ci = ctx.game_state.get_card_instance(inst_id)
            if ci:
                cd = ctx.game_state.get_card_data(ci.card_id)
                if cd and "tome" in cd.traits:
                    tome_count += 1
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_TOMES] = tome_count

    @on_event(
        GameEvent.SKILL_TEST_SUCCESSFUL,
        priority=TimingPriority.AFTER,
    )
    def elder_sign_draw(self, ctx):
        """远古印记检定成功：每控制1个典籍抽1张牌。"""
        inv = self._get_daisy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        tome_count = getattr(inv, "active_effects", {}).pop(_TOMES, 0)
        if not tome_count:
            return
        for _ in range(tome_count):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))
        ctx.game_state.log_effect(f"📚 黛西·沃克：远古印记成功，抽{tome_count}张牌")

    @on_event(
        GameEvent.SKILL_TEST_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_elder_sign_count(self, ctx):
        """检定结束：清除未消费的典籍计数（如检定失败）。"""
        for inv in ctx.game_state.investigators.values():
            if hasattr(inv, "active_effects"):
                inv.active_effects.pop(_TOMES, None)
