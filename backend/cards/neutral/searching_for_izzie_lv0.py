"""Searching for Izzie — Neutral Treachery, Signature Weakness (Jenny Barnes).
显现：将寻找伊莎贝拉叠加到离你最远的地点。
[action][action]：调查。如果成功，不获得线索，改为丢弃寻找伊莎贝拉。
强制 - 游戏结束时，如果寻找伊莎贝拉在场：珍妮·巴恩斯受到1点精神创伤。

简化说明：
- "最远的地点"用 BFS 连接距离计算。
- [action][action] 调查简化为：在该地点调查成功（CLUE_DISCOVERED 或
  SKILL_TEST_SUCCESSFUL 调查）时自动改为丢弃本卡（不花额外行动，不校验
  双行动消耗），由引擎的线索发现挂钩事后校正。
- 游戏结束的精神创伤由 game_end_penalty() 提供给会话层结算。
"""

from collections import deque

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SearchingForIzzie(CardImplementation):
    card_id = "searching_for_izzie_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "searching_for_izzie_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "searching_for_izzie_lv0" in inv.hand:
            inv.hand.remove("searching_for_izzie_lv0")

        target_loc = self._farthest_location(ctx.game_state, inv.location_id)

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="searching_for_izzie_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
            attached_to=target_loc,  # 叠加到的地点
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)
        ctx.game_state.scenario.vars["searching_for_izzie_location"] = target_loc

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def discard_on_investigate(self, ctx):
        """在叠加地点调查成功：不获得线索，改为丢弃寻找伊莎贝拉。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        izzie = self._find_izzie(ctx.game_state, inv)
        if izzie is None:
            return
        target_loc = ctx.game_state.scenario.vars.get("searching_for_izzie_location")
        if ctx.location_id != target_loc:
            return
        # 事后校正：取消线索获得
        loc = ctx.game_state.get_location(ctx.location_id)
        if loc is not None:
            loc.clues += ctx.amount or 1
        inv.clues = max(0, inv.clues - (ctx.amount or 1))
        # 丢弃寻找伊莎贝拉
        self._discard(ctx.game_state, inv, izzie)
        ctx.extra["searching_for_izzie_discarded"] = True

    def game_end_penalty(self, game_state, investigator_id) -> str | None:
        """游戏结束结算：寻找伊莎贝拉在场则受1点精神创伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        if self._find_izzie(game_state, inv) is not None:
            inv.mental_trauma = getattr(inv, "mental_trauma", 0) + 1
            return "寻找伊莎贝拉仍在场：受到1点精神创伤"
        return None

    @staticmethod
    def _find_izzie(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "searching_for_izzie_lv0":
                return inst
        return None

    @staticmethod
    def _discard(game_state, inv, inst):
        if inst.instance_id in inv.threat_area:
            inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        game_state.scenario.vars.pop("searching_for_izzie_location", None)
        inv.discard.append(inst.card_id)

    @staticmethod
    def _farthest_location(game_state, start_location_id) -> str:
        locations = game_state.locations
        if not locations:
            return start_location_id
        if start_location_id not in locations:
            return next(iter(locations))

        dist = {start_location_id: 0}
        queue = deque([start_location_id])
        while queue:
            current = queue.popleft()
            loc = locations.get(current)
            if loc is None:
                continue
            for nxt in getattr(loc, "connections", []) or []:
                if nxt in locations and nxt not in dist:
                    dist[nxt] = dist[current] + 1
                    queue.append(nxt)

        if len(dist) <= 1:
            for loc_id in locations:
                if loc_id != start_location_id:
                    return loc_id
            return start_location_id
        return max(dist, key=lambda k: dist[k])
