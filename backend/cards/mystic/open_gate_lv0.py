"""Open Gate (Level 0) — Mystic Event. (Spell, Myriad)
无数。快速。仅在你的回合中打出。
叠加到你的地点。场上限制3张。
调查员可以在任意两个叠加了开启之门的地点之间移动，视为这两个地点互相连接。

简化说明：
- 打出时创建叠加实例挂到所在地点（location.attachments）；场上已有3张时
  打出失效（直接入弃牌堆，官方为不可打出——打出前拦截需会话层支持）。
- 引擎 _move 在事件前先校验连接，卡无法扩展连接表（引擎缺口）；提供公开方法
  move_via_gate() 由会话层在常规移动之外调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance

GROUP_LIMIT = 3


class OpenGate(CardImplementation):
    card_id = "open_gate_lv0"

    @staticmethod
    def gated_locations(game_state) -> set[str]:
        """所有叠加了开启之门的地点 id。"""
        out = set()
        for loc in game_state.locations.values():
            for iid in loc.attachments:
                ci = game_state.get_card_instance(iid)
                if ci is not None and ci.card_id == "open_gate_lv0":
                    out.add(loc.location_id)
                    break
        return out

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_to_location(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None:
            return
        if len(self.gated_locations(ctx.game_state)) >= GROUP_LIMIT:
            ctx.extra["open_gate_fizzled_limit"] = True
            return
        inst = CardInstance(
            instance_id=ctx.game_state.next_instance_id(),
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            attached_to=loc.location_id,
        )
        ctx.game_state.cards_in_play[inst.instance_id] = inst
        loc.attachments.append(inst.instance_id)
        ctx.extra["open_gate_attached"] = loc.location_id

    def move_via_gate(self, game_state, investigator_id: str,
                      destination: str) -> bool:
        """经开启之门移动：当前地点与目的地都叠加了开启之门时视为连接。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or destination == inv.location_id:
            return False
        gated = self.gated_locations(game_state)
        if inv.location_id not in gated or destination not in gated:
            return False
        if game_state.get_location(destination) is None:
            return False
        inv.location_id = destination
        return True
