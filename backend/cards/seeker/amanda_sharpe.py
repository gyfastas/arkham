"""Amanda Sharpe — Seeker Investigator.
能力：强制 - 当调查阶段开始时：抽取1张卡牌。丢弃阿曼达‧夏普底下的卡牌。
选择你的一张手牌放置在她底下。
强制 - 当你执行的技能检定开始时：如果可能，投入阿曼达‧夏普底下的卡牌。
在检定结束时不要将其丢弃。
远古印记：+0。这次检定你可以将阿曼达‧夏普底下的卡牌的技能图标数量翻倍。

简化说明：
- "阿曼达底下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]（最多1张，
  与 sefina_rousseau / stars_of_hyades_lv0 共用的既定约定）。
- 调查阶段开始强制能力：INVESTIGATION_PHASE_BEGINS 为阶段级事件（不带
  investigator_id），按 mark_harrigan 惯例遍历调查员找到阿曼达结算。抽牌直接
  移动牌库顶到手牌、不发 CARD_DRAWN（避免递归触发抽牌显现类效果；抽到弱点
  不做搁置/显现处理——遗留简化，同 sefina 补抽）。
- "选择你的一张手牌放置在她底下"为玩家选择：优先读取一次性预设
  scenario.vars["amanda_sharpe_place"]（card_id，结算后弹出）；无预设时默认
  放置手牌第1张（官方为玩家任选）。
- "投入阿曼达底下的卡牌"：经 SKILL_TEST_COMMIT 的 ctx.amount（引擎的累计
  图标通道）加上该卡牌匹配当前检定的技能图标（含 wild）；卡牌本身留在阿曼达
  底下不入弃牌堆（官方 FAQ：检定结束时不丢弃）。被投卡牌自身的投入效果
  不触发——引擎缺口（ST.2 的正式投入通道不接收外来卡牌）。
- 远古印记的"图标翻倍"为可选但纯增益，简化为自动翻倍：SKILL_VALUE_DETERMINED
  时再加一份该卡牌的匹配图标。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class AmandaSharpe(CardImplementation):
    card_id = "amanda_sharpe"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._double_icons = False

    def _get_amanda(self, game_state, investigator_id):
        """Return the investigator state iff it is Amanda Sharpe."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "amanda_sharpe":
            return None
        return inv

    def _beneath_card(self, game_state, investigator_id) -> str | None:
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return None
        cards = scenario.vars.get(beneath_key(investigator_id), [])
        return cards[0] if cards else None

    def _icons_for(self, game_state, card_id, skill_type) -> int:
        if card_id is None or skill_type is None:
            return 0
        card_data = game_state.get_card_data(card_id)
        if card_data is None or not card_data.skill_icons:
            return 0
        return (
            card_data.skill_icons.get(skill_type.value, 0)
            + card_data.skill_icons.get("wild", 0)
        )

    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.FORCED)
    def investigation_phase_begins(self, ctx):
        """强制 - 调查阶段开始：抽1张牌，弃掉底下卡牌，从手牌选一张置于其下。"""
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return
        for inv_id, inv in ctx.game_state.investigators.items():
            card_data = getattr(inv, "card_data", None)
            if card_data is None or card_data.id != "amanda_sharpe":
                continue

            # 1) 抽1张牌
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))

            # 2) 弃掉阿曼达底下的卡牌
            key = beneath_key(inv_id)
            beneath = scenario.vars.get(key, [])
            old = beneath.pop(0) if beneath else None
            if old is not None:
                inv.discard.append(old)

            # 3) 从手牌选一张置于其下（预设优先，缺省取手牌第1张）
            preset = scenario.vars.pop("amanda_sharpe_place", None)
            if preset in inv.hand:
                chosen = preset
            else:
                chosen = inv.hand[0] if inv.hand else None
            if chosen is not None:
                inv.hand.remove(chosen)
                scenario.vars.setdefault(key, []).append(chosen)

            ctx.game_state.log_effect(
                f"🎓 阿曼达·夏普：调查阶段开始，抽1张牌"
                + (f"，弃掉底下的【{ctx.game_state.card_name(old)}】" if old else "")
                + (f"，将【{ctx.game_state.card_name(chosen)}】置于其下" if chosen else "")
            )

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def commit_beneath_card(self, ctx):
        """强制 - 检定开始：投入阿曼达底下的卡牌（加上其匹配图标；卡不离开底下）。"""
        inv = self._get_amanda(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        beneath = self._beneath_card(ctx.game_state, ctx.investigator_id)
        icons = self._icons_for(ctx.game_state, beneath, ctx.skill_type)
        if icons > 0:
            ctx.modify_amount(icons, "amanda_sharpe_beneath")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+0。本次检定将底下卡牌的技能图标翻倍（自动，纯增益）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_amanda(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        if self._beneath_card(ctx.game_state, ctx.investigator_id) is not None:
            self._double_icons = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_doubled_icons(self, ctx):
        """远古印记：底下卡牌的图标再加一份（翻倍）。"""
        if not self._double_icons:
            return
        inv = self._get_amanda(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        beneath = self._beneath_card(ctx.game_state, ctx.investigator_id)
        icons = self._icons_for(ctx.game_state, beneath, ctx.skill_type)
        if icons > 0:
            ctx.modify_amount(icons, "amanda_sharpe_elder_sign_double")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._double_icons = False
