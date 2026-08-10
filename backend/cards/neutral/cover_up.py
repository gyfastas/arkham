"""Cover Up — Neutral Treachery, Signature Weakness (Roland Banks).
揭示：放入你的威胁区域，上面放置3个线索。
强制 - 当你将要从所在地点发现1个或以上线索时：改为从掩盖真相上弃掉等量线索。
强制 - 游戏结束时，如果掩盖真相上仍有线索：你受到1点精神创伤。

简化说明：
- 线索重定向通过 CLUE_DISCOVERED(WHEN) 事后校正实现（引擎先结算发现线索，
  本实现把线索放回地点并从掩盖真相上弃掉等量线索）。
- 游戏结束的精神创伤由 game_end_penalty() 提供给会话层结算（引擎无 GAME_ENDS 事件）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CoverUp(CardImplementation):
    card_id = "cover_up"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "cover_up":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "cover_up" in inv.hand:
            inv.hand.remove("cover_up")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="cover_up",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ci.uses = {"clues": 3}
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def redirect_clues(self, ctx):
        """当你将要从所在地点发现线索时：改为从掩盖真相上弃掉等量线索。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 卡面限定"在你的地点"：在其他地点发现线索（如指导、解码器）不触发
        if ctx.location_id is not None and ctx.location_id != inv.location_id:
            return
        cover_up = self._find_cover_up(ctx.game_state, inv)
        if cover_up is None:
            return
        remaining = cover_up.uses.get("clues", 0)
        if remaining <= 0:
            return
        amount = min(ctx.amount or 1, remaining)
        loc = ctx.game_state.get_location(ctx.location_id) if ctx.location_id else None
        if loc is None:
            loc = ctx.game_state.get_location(inv.location_id)
        # 事后校正：把线索放回地点，从掩盖真相弃掉
        if loc is not None:
            loc.clues += amount
        inv.clues = max(0, inv.clues - amount)
        cover_up.uses["clues"] = remaining - amount
        ctx.extra["cover_up_redirected"] = amount

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束结算：掩盖真相上仍有线索则受1点精神创伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        cover_up = self._find_cover_up(game_state, inv)
        if cover_up is not None and cover_up.uses.get("clues", 0) > 0:
            inv.mental_trauma = getattr(inv, "mental_trauma", 0) + 1
            return "掩盖真相上仍有线索：受到1点精神创伤"
        return None

    @staticmethod
    def _find_cover_up(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "cover_up":
                return inst
        return None
