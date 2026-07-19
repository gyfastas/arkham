"""Arcane Initiate (Level 0) — Mystic Asset, Ally slot.
强制 - 在刷新阶段开始时：弃置新晋术士或在其上放置1点恐惧。
反应 - 在新晋术士进场时或在其上有恐惧放置时：搜索你的牌库，将一张法术支援卡加入手牌，然后洗牌。

简化说明：
- 刷新阶段的"弃置或放恐惧"自动选择放恐惧。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class ArcaneInitiate(CardImplementation):
    card_id = "arcane_initiate_lv0"

    def _search_spell(self, game_state, inv) -> str | None:
        """从牌库搜索一张法术支援卡加入手牌，然后洗牌。"""
        for i, card_id in enumerate(inv.deck):
            cd = game_state.get_card_data(card_id)
            if cd is None or cd.type != CardType.ASSET:
                continue
            if "spell" in (cd.traits or []):
                inv.deck.pop(i)
                inv.hand.append(card_id)
                random.shuffle(inv.deck)
                return card_id
        random.shuffle(inv.deck)
        return None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """进场时：搜索法术支援卡。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        found = self._search_spell(ctx.game_state, inv)
        if found:
            ctx.extra["arcane_initiate_found"] = found
            ctx.game_state.log_effect(
                f"🔮 新晋术士：搜索牌库，找到【{ctx.game_state.card_name(found)}】")

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def upkeep_horror(self, ctx):
        """刷新阶段开始时：在其上放置1点恐惧（并触发搜索）。"""
        for inv in ctx.game_state.investigators.values():
            if self.instance_id not in inv.play_area:
                continue
            inst = ctx.game_state.get_card_instance(self.instance_id)
            if inst is None:
                continue
            inst.horror += 1
            # 有恐惧放置时：搜索法术支援卡
            self._search_spell(ctx.game_state, inv)
