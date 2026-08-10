"""Tony Morgan — Rogue Investigator.
能力：在你的回合中你可以进行一次额外的行动，该行动只能用于攻击一名带有赏金的
敌人或与其交战。
远古印记：+2。在赏金合约上放置1赏金。

简化说明：
- 额外行动在 INVESTIGATOR_TURN_BEGINS 时授予（actions_remaining += 1）；
  "只能用于攻击/交战带赏金的敌人"的限制无法在不修改 engine/actions.py 行动
  扣减流程的前提下强制执行——引擎缺口，当前额外行动不限制用途。
- 赏金计数沿用 bounty_contracts_lv0 的既定约定：敌人赏金存 uses["bounties"]，
  赏金合约自身的赏金存其实例 uses（数据 JSON 键名有 "bountiess" 笔误，读取时
  兼容两种键名，写入统一规范化为 "bounties"）。
- 远古印记的"在赏金合约上放置1赏金"：自动放到托尼控制的赏金合约实例上；
  合约不在场时无法放置（跳过并记录日志）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

BOUNTY_CONTRACTS_ID = "bounty_contracts_lv0"


class TonyMorgan(CardImplementation):
    card_id = "tony_morgan"

    def _get_tony(self, game_state, investigator_id):
        """Return the investigator state iff it is Tony Morgan."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "tony_morgan":
            return None
        return inv

    def _find_contracts(self, game_state, inv):
        """托尼控制的赏金合约实例（在场的第一张）。"""
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == BOUNTY_CONTRACTS_ID:
                return inst
        return None

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def grant_extra_action(self, ctx):
        """每个回合获得1个额外行动（用途限制未强制，见文件头）。"""
        inv = self._get_tony(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        inv.actions_remaining += 1
        ctx.game_state.log_effect("🔫 托尼·摩尔根：获得1个额外行动（限攻击/交战带赏金的敌人）")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。在赏金合约上放置1赏金。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_tony(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "tony_morgan_elder_sign")

        contracts = self._find_contracts(ctx.game_state, inv)
        if contracts is None:
            ctx.game_state.log_effect("🔫 托尼·摩尔根：赏金合约不在场，无法放置赏金")
            return
        available = contracts.uses.get("bounties", contracts.uses.get("bountiess", 0))
        contracts.uses["bounties"] = available + 1
        contracts.uses.pop("bountiess", None)
        ctx.game_state.log_effect("🔫 托尼·摩尔根：远古印记，在赏金合约上放置1赏金")
