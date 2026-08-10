"""Jeremiah Kirby (Level 0) — Seeker Asset, Ally slot. (08032)
你获得+1智力。
[反应]在耶利米·科尔比入场后，选择"偶数"或"奇数"：揭示你牌堆顶部的5张
卡牌。抽取费用符合你所选择的每张卡牌。将剩余卡牌与你的牌堆混洗。

简化说明：
- "+1智力"为常驻加值（SKILL_VALUE_DETERMINED，与 dr_milan 一致）；
- 奇偶自动选择抽牌数较多的一侧（平手取偶数；官方为玩家自选），可用
  ctx.extra["parity"]（"even"/"odd"）或公开方法 reveal_top(parity=...) 指定；
- 无费用（cost=None）的卡牌两种奇偶都不符合，留牌堆（官方规则）；
- 剩余卡牌混洗回牌堆（random.shuffle）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class JeremiahKirby(CardImplementation):
    card_id = "jeremiah_kirby_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._entered = False

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        if ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "jeremiah_kirby_intellect")

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def on_enters_play(self, ctx):
        """入场后反应：自动选择奇偶并揭示牌堆顶5张抽牌。"""
        if ctx.target != self.instance_id:
            return
        parity = ctx.extra.get("parity")
        self.reveal_top(ctx.game_state, ctx.investigator_id, parity=parity)

    def reveal_top(self, game_state, investigator_id: str,
                   parity: str | None = None) -> bool:
        """揭示牌堆顶5张：抽取费用匹配奇偶的卡，其余混洗回牌堆。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._entered:
            return False
        if not inv.deck:
            return False
        self._entered = True

        top = list(inv.deck[:5])
        rest = list(inv.deck[5:])

        def matches(cid: str, p: str) -> bool:
            cd = game_state.get_card_data(cid)
            cost = cd.cost if cd is not None else None
            if cost is None:
                return False
            return (cost % 2 == 0) if p == "even" else (cost % 2 == 1)

        if parity not in ("even", "odd"):
            even_hits = sum(1 for c in top if matches(c, "even"))
            odd_hits = sum(1 for c in top if matches(c, "odd"))
            parity = "even" if even_hits >= odd_hits else "odd"

        # 按索引划分，避免重复卡 id 互相误删
        drawn, remaining = [], []
        for c in top:
            (drawn if matches(c, parity) else remaining).append(c)

        inv.hand.extend(drawn)
        inv.deck = rest + remaining
        random.shuffle(inv.deck)
        game_state.log_effect(
            f"🔎 耶利米·科尔比：选择{'偶数' if parity == 'even' else '奇数'}，"
            f"揭示顶{len(top)}张，抽取{len(drawn)}张"
        )
        return True
