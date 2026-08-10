"""Grisly Totem (Level 3) — Seeker Asset, Accessory slot. (05194)
[反应]在你将一张卡牌投入技能检定后，消耗恐怖图腾：你选择该卡牌已有的
任意一个技能图标，该卡牌额外获得该图标。如果该技能检定成功，执行该
检定的调查员抽取1张卡牌。

简化说明：
- "额外获得1个已有图标"自动选择：优先与本次检定技能匹配的图标，
  否则万能图标；两者皆无时不消耗本卡（官方为玩家自选图标）；
- 多卡同时投入时以最后投入的那张为准（引擎 SKILL_TEST_COMMIT 一次
  携带全部投入卡）；
- 加图标实现为 SKILL_TEST_COMMIT 时 committed_icons +1（引擎 ST.2 读取
  ctx.amount）；成功抽牌直接自牌堆顶抽取（不发 CARD_DRAWN，已知简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GrislyTotem(CardImplementation):
    card_id = "grisly_totem_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._draw_pending: str | None = None

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def add_icon(self, ctx):
        """你投入卡牌后：消耗本卡，该卡额外获得1个匹配图标。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or not ctx.committed_cards:
            return

        card_id = ctx.committed_cards[-1]
        cd = ctx.game_state.get_card_data(card_id)
        icons = (cd.skill_icons or {}) if cd else {}
        skill_key = ctx.skill_type.value if ctx.skill_type is not None else ""
        if icons.get(skill_key, 0) < 1 and icons.get("wild", 0) < 1:
            return

        inst.exhausted = True
        ctx.modify_amount(1, "grisly_totem_extra_icon")
        self._draw_pending = ctx.investigator_id
        ctx.extra["grisly_totem_boosted"] = card_id
        ctx.game_state.log_effect(
            f"🗿 恐怖图腾：【{ctx.game_state.card_name(card_id)}】额外获得1个图标"
        )

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def draw_on_success(self, ctx):
        """该技能检定成功：执行检定的调查员抽1张牌。"""
        if self._draw_pending != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["grisly_totem_drew"] = True
            ctx.game_state.log_effect("🗿 恐怖图腾：检定成功，抽取1张卡牌")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._draw_pending = None
