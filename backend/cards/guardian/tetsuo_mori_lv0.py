"""Tetsuo Mori (Level 0) — Guardian Asset, Ally slot. (06155)
对你所在地点其他调查员造成的伤害和/或恐惧，可以分配给森哲夫。
[反应]在森哲夫被击败时：选择你所在地点的一位调查员。该调查员在其弃牌堆
或牌堆顶部9张卡牌中查找一张[[道具]]支援卡，并加入其手牌。如果查找了牌堆，将其混洗。

简化说明：
- 伤害/恐惧转移：引擎 DamageEngine.deal_damage 的 damage_assignment /
  horror_assignment 通道不校验承伤支援的归属，会话层为同地点其他调查员
  传入森哲夫的 instance_id 即可分配（get_ally_soak_targets 只列受伤者自己
  的支援，UI 枚举缺口见报告）；本文件无需额外代码。
- 击败时的查找：默认由森哲夫的拥有者先查弃牌堆、未命中再查牌堆顶9张
  （官方为玩家选择调查员与查找哪一处）。会话层可在击败前写入
  scenario.vars["tetsuo_mori_choice"] = {"investigator_id": ..., "source":
  "discard"|"deck"} 覆盖默认选择（显式指定来源未命中时不兜底另一处）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_CHOICE_VAR = "tetsuo_mori_choice"


class TetsuoMori(CardImplementation):
    card_id = "tetsuo_mori_lv0"

    @on_event(GameEvent.ASSET_DEFEATED, priority=TimingPriority.AFTER)
    def search_on_defeat(self, ctx):
        """被击败时：所选调查员查找一张道具支援卡加入手牌。"""
        if ctx.target != self.instance_id:
            return
        game_state = ctx.game_state
        # 击败事件在实例移除前发出（DamageEngine 先 emit 再移除），仍可读到归属
        inst = game_state.get_card_instance(self.instance_id)

        choice = game_state.scenario.vars.pop(_CHOICE_VAR, None) or {}
        inv = None
        if choice.get("investigator_id"):
            inv = game_state.get_investigator(choice["investigator_id"])
        if inv is None and inst is not None:
            inv = game_state.get_investigator(inst.owner_id)
        if inv is None:
            return

        source = choice.get("source")
        found = None
        if source in (None, "discard"):
            found = self._search_discard(game_state, inv)
        if found is None and source in (None, "deck"):
            found = self._search_deck(game_state, inv)
        if found is None:
            return
        ctx.extra["tetsuo_mori_found"] = found
        game_state.log_effect(
            f"👮 森哲夫：被击败，查找到【{game_state.card_name(found)}】加入手牌")

    @staticmethod
    def _is_item_asset(game_state, card_id: str) -> bool:
        data = game_state.get_card_data(card_id)
        if data is None or data.type != CardType.ASSET:
            return False
        traits = {t.lower() for t in (data.traits or [])}
        return "item" in traits

    def _search_discard(self, game_state, inv) -> str | None:
        for card_id in list(inv.discard):
            if self._is_item_asset(game_state, card_id):
                inv.discard.remove(card_id)
                inv.hand.append(card_id)
                return card_id
        return None

    def _search_deck(self, game_state, inv) -> str | None:
        for card_id in list(inv.deck[:9]):
            if self._is_item_asset(game_state, card_id):
                inv.deck.remove(card_id)
                inv.hand.append(card_id)
                random.shuffle(inv.deck)
                return card_id
        return None
