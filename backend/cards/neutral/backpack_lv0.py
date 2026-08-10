"""Backpack (Level 0) — Neutral Asset.
[reaction] 背包入场后：从你的牌组顶6张牌中搜寻至多3张非弱点[[Item]]或
[[Supply]]卡，背面朝上附着到背包上。洗混你的牌组。
附着于背包的卡牌可以像在你手牌中一样被打出。若背包上没有附着卡牌，丢弃它。

简化说明：
- 附着的卡（背面朝上）以 card_id 列表存放在
  scenario.vars["backpack_{instance_id}"]（与 stars_of_hyades_lv0 的
  beneath 同一惯例）。
- "附着卡可像手牌一样打出"由会话层实现：attached_cards() 返回可打牌列表，
  打出后调用 remove_attached() 移除并检查空背包自弃。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

SEARCH_DEPTH = 6
MAX_ATTACHED = 3
_ALLOWED_TRAITS = {"item", "supply"}


def _vars_key(instance_id: str) -> str:
    return f"backpack_{instance_id}"


class Backpack(CardImplementation):
    card_id = "backpack_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def attach_from_deck(self, ctx):
        """入场后：牌组顶6张中搜寻至多3张非弱点物品/补给，背面附着。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.card_id != "backpack_lv0":
            return
        inv = ctx.game_state.get_investigator(inst.owner_id)
        if inv is None:
            return

        from backend.models.state import is_weakness_card
        top = inv.deck[:SEARCH_DEPTH]
        rest = inv.deck[SEARCH_DEPTH:]
        attached: list[str] = []
        kept: list[str] = []
        for cid in top:
            cd = ctx.game_state.get_card_data(cid)
            ok = (
                cd is not None
                and not is_weakness_card(cd)
                and _ALLOWED_TRAITS & set(cd.traits or [])
            )
            if ok and len(attached) < MAX_ATTACHED:
                attached.append(cid)
            else:
                kept.append(cid)
        inv.deck = kept + rest
        random.shuffle(inv.deck)

        ctx.game_state.scenario.vars[_vars_key(self.instance_id)] = attached
        ctx.extra["backpack_attached"] = attached
        if attached:
            ctx.game_state.log_effect(
                f"🎒 背包：附着 {len(attached)} 张卡（背面朝上）")
        else:
            # 没有附着任何卡：背包立即自弃
            self._discard_backpack(ctx.game_state, inv)

    # ------------------------------------------------------------------
    # 会话层接口
    # ------------------------------------------------------------------

    def attached_cards(self, game_state) -> list[str]:
        """附着于背包的卡（可像手牌一样打出）。"""
        return list(game_state.scenario.vars.get(_vars_key(self.instance_id), []))

    def remove_attached(self, game_state, card_id: str) -> bool:
        """打出附着卡后移除；背包无附着卡时丢弃背包。"""
        key = _vars_key(self.instance_id)
        attached = game_state.scenario.vars.get(key, [])
        if card_id not in attached:
            return False
        attached.remove(card_id)
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(inst.owner_id) if inst else None
        if not attached and inv is not None:
            self._discard_backpack(game_state, inv)
        return True

    def _discard_backpack(self, game_state, inv) -> None:
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append("backpack_lv0")
        game_state.scenario.vars.pop(_vars_key(self.instance_id), None)
        game_state.log_effect("🎒 背包：无附着卡，丢弃背包")
