"""温蒂的护身符（Wendy's Amulet）— 温蒂·亚当斯专属支援卡，饰品。
你可以将弃牌堆最上面的事件牌当作手牌来打出。
强制 - 在你打出一张事件牌或从场上弃置一张事件牌后：将其放到你的牌堆
底部，而非弃牌堆。

简化说明：
- "从弃牌堆打出"实现为 play_top_event_from_discard() 方法，由会话层/UI
  调用：将弃牌堆顶的事件牌移入手牌后走正常打出流程（支付费用、消耗行动）。
  JSON 未限制每轮次数，故不设每轮限次。
- 强制效果：引擎在 CARD_PLAYED 事件之后才将事件牌置入弃牌堆，无法在该
  事件内拦截，因此先记录标记，在紧随的 ACTION_PERFORMED 时把该事件从
  弃牌堆移到牌堆底；若本回合未触发 ACTION_PERFORMED（非常规打出路径），
  则在 ROUND_ENDS 时清理标记以免误伤后续弃牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_PENDING_KEY = "wendys_amulet_pending_bottom"


class WendysAmulet(CardImplementation):
    card_id = "wendys_amulet"

    # ------------------------------------------------------------------
    # 从弃牌堆顶打出事件（由会话层调用）
    # ------------------------------------------------------------------

    def top_event_in_discard(self, game_state, investigator_id: str) -> str | None:
        """返回控制者弃牌堆最上面的事件牌 card_id（无则 None）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        for card_id in reversed(inv.discard):
            card_data = game_state.get_card_data(card_id)
            if card_data is not None and card_data.type == CardType.EVENT:
                return card_id
        return None

    def play_top_event_from_discard(self, game, investigator_id: str) -> bool:
        """将弃牌堆顶的事件牌当作手牌打出（走正常 PLAY 流程）。"""
        card_id = self.top_event_in_discard(game.state, investigator_id)
        if card_id is None:
            return False
        inv = game.state.get_investigator(investigator_id)
        inv.discard.remove(card_id)
        inv.hand.append(card_id)
        from backend.models.enums import Action
        ok = game.action_resolver.perform_action(
            investigator_id, Action.PLAY, card_id=card_id,
        )
        if not ok and card_id in inv.hand:
            inv.hand.remove(card_id)
            inv.discard.append(card_id)
        return ok

    # ------------------------------------------------------------------
    # 强制效果：打出的事件放到牌堆底部而非弃牌堆
    # ------------------------------------------------------------------

    @on_event(
        GameEvent.CARD_PLAYED,
        priority=TimingPriority.AFTER,
    )
    def mark_played_event(self, ctx):
        """Record the event the controller just played (engine discards it
        only after CARD_PLAYED resolves, so we defer the move)."""
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        card_data = ctx.game_state.get_card_data(card_id)
        if card_data is None or card_data.type != CardType.EVENT:
            return
        ctx.game_state.scenario.vars[_PENDING_KEY] = (ctx.investigator_id, card_id)

    @on_event(
        GameEvent.ACTION_PERFORMED,
        priority=TimingPriority.AFTER,
    )
    def move_event_to_deck_bottom(self, ctx):
        """Place the just-played event on the bottom of the deck instead of
        the discard pile."""
        pending = ctx.game_state.scenario.vars.pop(_PENDING_KEY, None)
        if not pending:
            return
        inv_id, card_id = pending
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is None:
            return
        if card_id in inv.discard:
            inv.discard.remove(card_id)
        if card_id not in inv.deck:
            inv.deck.append(card_id)

    @on_event(
        GameEvent.CARD_LEAVES_PLAY,
        priority=TimingPriority.AFTER,
    )
    def move_discarded_event_to_deck_bottom(self, ctx):
        """Forced: after you discard an event from play, place it on the
        bottom of your deck instead of in your discard pile.

        注：当前引擎没有"事件牌在场"的机制（事件结算后即进弃牌堆），
        该触发在生产链路中暂不可达；若引擎日后支持场上事件，此处即生效。
        """
        card_id = ctx.extra.get("card_id")
        if not card_id or card_id == "wendys_amulet":
            return
        card_data = ctx.game_state.get_card_data(card_id)
        if card_data is None or card_data.type != CardType.EVENT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if card_id in inv.discard:
            inv.discard.remove(card_id)
        if card_id not in inv.deck:
            inv.deck.append(card_id)

    @on_event(
        GameEvent.ROUND_ENDS,
        priority=TimingPriority.AFTER,
    )
    def clear_stale_mark(self, ctx):
        """Clear a stale mark if the play never produced an ACTION_PERFORMED."""
        ctx.game_state.scenario.vars.pop(_PENDING_KEY, None)
