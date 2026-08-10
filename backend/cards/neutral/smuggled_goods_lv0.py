"""Smuggled Goods (Level 0) — Neutral Event. (04010)
仅限芬恩·爱德华兹牌组。
仅在你所在地点没有就绪敌人时打出。
检索你的弃牌堆或你牌堆顶9张卡牌中的一张[[违禁品]]卡并抽取它。若你检索了
牌组，将走私货物洗入你的牌组。

简化说明：
- "仅限芬恩牌组"为构筑限制，由卡组校验负责。
- 检索目标自动选择：优先弃牌堆中的第一张违禁品卡；弃牌堆没有时检索牌堆
  顶9张（官方为玩家选择来源与目标）。
- 打出限制（同地点无就绪敌人）在 handler 内校验：有就绪敌人则效果不发动。
- "洗入牌组而非弃置"：actions._play_event 在 CARD_PLAYED 结算后无条件将
  事件放入弃牌堆，handler 内无法拦截（引擎缺口）；会话层应在结算后调用
  resolve_shuffle_back() 完成洗回。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SmuggledGoods(CardImplementation):
    card_id = "smuggled_goods_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "smuggled_goods_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 打出限制：你所在地点没有就绪敌人
        if self._ready_enemy_at_location(ctx.game_state, inv):
            ctx.extra["smuggled_goods_fizzled"] = True
            return

        found = None
        searched_deck = False
        # 1. 弃牌堆
        for cid in inv.discard:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and "illicit" in (cd.traits or []):
                found = cid
                break
        # 2. 牌堆顶9张
        if found is None:
            for cid in inv.deck[:9]:
                cd = ctx.game_state.get_card_data(cid)
                if cd is not None and "illicit" in (cd.traits or []):
                    found = cid
                    searched_deck = True
                    break

        if found is not None:
            if searched_deck:
                inv.deck.remove(found)
                random.shuffle(inv.deck)
            else:
                inv.discard.remove(found)
            inv.hand.append(found)
        ctx.extra["smuggled_goods_found"] = found
        ctx.extra["smuggled_goods_searched_deck"] = searched_deck and found is not None

    def resolve_shuffle_back(self, game_state, investigator_id) -> bool:
        """检索了牌组时：将本卡从弃牌堆洗回牌组（会话层在结算后调用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "smuggled_goods_lv0" not in inv.discard:
            return False
        inv.discard.remove("smuggled_goods_lv0")
        inv.deck.append("smuggled_goods_lv0")
        random.shuffle(inv.deck)
        return True

    @staticmethod
    def _ready_enemy_at_location(game_state, inv) -> bool:
        from backend.models.enums import CardType
        location = game_state.get_location(inv.location_id)
        candidates = []
        if location is not None:
            candidates.extend(location.enemies)
        candidates.extend(inv.threat_area)
        for iid in candidates:
            inst = game_state.get_card_instance(iid)
            cd = game_state.get_card_data(inst.card_id) if inst else None
            if inst is None or cd is None or cd.type != CardType.ENEMY:
                continue
            if not inst.exhausted:
                return True
        return False
