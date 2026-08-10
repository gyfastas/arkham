"""Daredevil (Level 2) — Rogue Skill. (06240)
在你投入虎口拔牙到技能检定后，从你的牌堆顶部揭示卡牌，直到你揭示了能投入
到这次检定的[流浪者]技能卡。将其投入。将其它每张已揭示卡牌混洗回你的牌堆。

简化说明：
- "能投入到这次检定的[流浪者]技能卡"简化为牌堆中第一张流浪者技能卡
  （官方含投入限制校验，如"仅限你自己的检定"等，由会话层负责）。
- 被投入的技能只计图标（经 ctx.modify_amount）；该技能自身的投入效果不会
  激活（引擎的临时实例在 ST.2 前已建立——简化注明）。
- 其它已揭示卡牌洗回牌堆（整堆 random.shuffle，分布等价）。
- 投入的卡来自牌堆而非手牌：ST.8 引擎只从手牌弃置投入卡，故本实现在
  SKILL_TEST_ENDS 将其置入弃牌堆（官方流程）。
- 持久实例与临时实例可能同时收到 SKILL_TEST_COMMIT，经 ctx.extra 去重
  （take_the_initiative 同模式）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, PlayerClass, TimingPriority


class Daredevil(CardImplementation):
    card_id = "daredevil_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._committed_from_deck: tuple[str, str] | None = None  # (inv_id, card_id)

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def reveal_and_commit(self, ctx):
        """投入后：揭示牌堆顶直至流浪者技能，将其投入，其余洗回。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        if ctx.extra.get("daredevil_applied"):
            return  # 持久/临时实例去重
        ctx.extra["daredevil_applied"] = True
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.deck:
            return

        revealed_others: list[str] = []
        found: str | None = None
        while inv.deck:
            card_id = inv.deck.pop(0)
            cd = ctx.game_state.get_card_data(card_id)
            if (
                cd is not None
                and cd.type == CardType.SKILL
                and cd.card_class == PlayerClass.ROGUE
                and card_id != self.card_id
            ):
                found = card_id
                break
            revealed_others.append(card_id)

        # 其它已揭示卡牌洗回牌堆
        if revealed_others:
            inv.deck.extend(revealed_others)
            random.shuffle(inv.deck)

        if found is None:
            ctx.game_state.log_effect("🎯 虎口拔牙：牌堆中没有可投入的流浪者技能")
            return

        # 将其投入：计入图标并登记，检定结束后弃置。
        # 注：不写入 ctx.committed_cards——引擎 ST.8 会把列表中的卡从手牌
        # 弃置，而此卡来自牌堆（可能误弃手牌中的同名卡）；改经 extra 登记。
        cd = ctx.game_state.get_card_data(found)
        icons = 0
        if cd is not None and ctx.skill_type is not None:
            icons = cd.skill_icons.get(ctx.skill_type.value, 0)
            icons += cd.skill_icons.get("wild", 0)
        if icons:
            ctx.modify_amount(icons, "daredevil_committed_icons")
        self._committed_from_deck = (inv.investigator_id, found)
        ctx.extra["daredevil_committed"] = found
        ctx.game_state.log_effect(
            f"🎯 虎口拔牙：揭示并投入【{ctx.game_state.card_name(found)}】"
            f"（+{icons}图标），其余{len(revealed_others)}张洗回牌堆")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_committed(self, ctx):
        """检定结束：从牌堆投入的技能置入弃牌堆。"""
        if self._committed_from_deck is None:
            return
        inv_id, card_id = self._committed_from_deck
        self._committed_from_deck = None
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None:
            return
        # 来自牌堆的那张在 ST.8 不经手牌弃置，这里补入弃牌堆
        if card_id not in inv.discard:
            inv.discard.append(card_id)
