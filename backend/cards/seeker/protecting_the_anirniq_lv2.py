"""Protecting the Anirniq (Level 2) — Seeker Event, Fast. (08102)
快速。在你所在地点一张[[盟友]]支援卡被卡牌效果丢弃或被击败后打出。
将该支援卡返回其所有者的手中，或其所有者抽取3张卡牌。

简化说明：
- 打出时机由会话层校验（引擎无"盟友刚离场"的打出窗口）；
- "该支援卡"由 ctx.extra["ally_card_id"] 指定；缺省自动选取你所在地点
  调查员弃牌堆中最近的一张[[盟友]]支援卡；
- 模式二选一：ctx.extra["anirniq_mode"]="draw" 时其所有者抽3张，
  缺省为返回所有者手牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class ProtectingTheAnirniq(CardImplementation):
    card_id = "protecting_the_anirniq_lv2"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def protect(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        found = self._find_ally(ctx, inv)
        if found is None:
            ctx.extra["anirniq_failed"] = "no_ally"
            return
        owner, ally_card_id = found

        if ctx.extra.get("anirniq_mode") == "draw":
            for _ in range(3):
                if owner.deck:
                    owner.hand.append(owner.deck.pop(0))
            ctx.extra["anirniq_mode_used"] = "draw"
            ctx.game_state.log_effect(
                f"🛡️ 保护魂灵：【{ctx.game_state.card_name(ally_card_id)}】"
                f"的所有者抽3张牌")
        else:
            if ally_card_id in owner.discard:
                owner.discard.remove(ally_card_id)
            owner.hand.append(ally_card_id)
            ctx.extra["anirniq_mode_used"] = "return"
            ctx.game_state.log_effect(
                f"🛡️ 保护魂灵：【{ctx.game_state.card_name(ally_card_id)}】"
                "返回其所有者手牌")

    def _find_ally(self, ctx, inv):
        """(owner, ally_card_id)：extra 指定或各调查员弃牌堆中最近的盟友。"""
        wanted = ctx.extra.get("ally_card_id")
        for other in ctx.game_state.investigators.values():
            if other.location_id != inv.location_id:
                continue
            if wanted is not None and wanted in other.discard:
                cd = ctx.game_state.get_card_data(wanted)
                if self._is_ally(cd):
                    return other, wanted
                return None
            if wanted is None:
                for card_id in reversed(other.discard):
                    cd = ctx.game_state.get_card_data(card_id)
                    if cd is not None and cd.type == CardType.ASSET:
                        if self._is_ally(cd):
                            return other, card_id
                        break  # 只看各弃牌堆顶最近的支援
        return None

    @staticmethod
    def _is_ally(cd) -> bool:
        return (
            cd is not None
            and cd.type == CardType.ASSET
            and "ally" in (cd.traits or [])
        )
