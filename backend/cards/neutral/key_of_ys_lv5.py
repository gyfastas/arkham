"""Key of Ys (Level 5) — Neutral Asset.
伊苏之匙上每有1点恐惧，你每项技能+1。
强制 - 任意数量的恐惧将要放置到你身上时：将其中1点恐惧放置到伊苏之匙上。
强制 - 伊苏之匙离场时：丢弃你牌堆顶的10张卡牌。

简化说明：
- 恐惧重定向挂 HORROR_ASSIGNED（engine.damage 的非直接伤害通道）；直接恐惧
  （各卡实现里 inv.horror += N）不经过事件总线，无法拦截。
- 经本卡强制能力放置的恐惧若使伊苏之匙恐惧达到理智上限，立即按战败离场处理
  并触发离场效果（引擎的资产战败检查只在 deal_damage 通道内做）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class KeyOfYs(CardImplementation):
    card_id = "key_of_ys_lv5"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_boost(self, ctx):
        """伊苏之匙上每有1点恐惧，你每项技能+1。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        if inst.horror > 0:
            ctx.modify_amount(inst.horror, "key_of_ys_horror_boost")

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def redirect_horror(self, ctx):
        """强制：将要放置到你身上的恐惧，其中1点放到伊苏之匙上。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        if (ctx.amount or 0) < 1:
            return
        ctx.modify_amount(-1, "key_of_ys_absorb")
        inst.horror += 1
        ctx.game_state.log_effect("🗝️ 伊苏之匙：1点恐惧转移到伊苏之匙上")
        # 恐惧达到理智上限：战败离场（触发离场效果）
        cd = ctx.game_state.get_card_data(inst.card_id)
        if cd is not None and cd.sanity is not None and inst.horror >= cd.sanity:
            inv = ctx.game_state.get_investigator(inst.owner_id)
            if inv is not None and inst.instance_id in inv.play_area:
                inv.play_area.remove(inst.instance_id)
            ctx.game_state.cards_in_play.pop(inst.instance_id, None)
            if inv is not None:
                inv.discard.append(inst.card_id)
            self._discard_top_cards(ctx.game_state, inst.owner_id)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def on_leaves_play(self, ctx):
        """强制：伊苏之匙离场时，丢弃你牌堆顶的10张卡牌。"""
        if ctx.target != self.instance_id:
            return
        self._discard_top_cards(ctx.game_state, ctx.investigator_id)

    @staticmethod
    def _discard_top_cards(game_state, owner_id, count: int = 10) -> None:
        inv = game_state.get_investigator(owner_id)
        if inv is None:
            return
        for _ in range(min(count, len(inv.deck))):
            inv.discard.append(inv.deck.pop(0))
        game_state.log_effect("🗝️ 伊苏之匙离场：丢弃牌堆顶的10张卡牌")
