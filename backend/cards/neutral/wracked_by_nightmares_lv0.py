"""Wracked by Nightmares — Neutral Treachery, Signature Weakness ("Ashcan" Pete).
显现：消耗你控制的所有支援卡，并将噩梦来袭放置入你的威胁区域。
你控制的支援卡不能准备。
[action][action]：丢弃噩梦来袭。

简化说明：
- "不能准备"通过 CARD_READIED(AFTER) 重新横置实现（引擎刷新流程先就绪再发事件）。
- [action][action] 丢弃实现为 activate_discard() 公开方法（行动消耗由会话层校验）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class WrackedByNightmares(CardImplementation):
    card_id = "wracked_by_nightmares_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃噩梦来袭", "method": "activate_discard", "actions": 2}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "wracked_by_nightmares_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "wracked_by_nightmares_lv0" in inv.hand:
            inv.hand.remove("wracked_by_nightmares_lv0")

        # 消耗（横置）你控制的所有支援卡
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is not None and inst.controller_id == inv.investigator_id:
                inst.exhausted = True

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="wracked_by_nightmares_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def prevent_ready(self, ctx):
        """你控制的支援卡不能准备（就绪后重新横置）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id) if ctx.investigator_id else None
        # 无 investigator_id 时对持有者检查
        target = ctx.game_state.get_card_instance(ctx.target) if ctx.target else None
        if target is None:
            return
        owner_id = target.controller_id
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is None:
            return
        if self._find_nightmares(ctx.game_state, owner) is None:
            return
        if target.instance_id not in owner.play_area:
            return
        target.exhausted = True
        ctx.extra["wracked_by_nightmares_prevented_ready"] = True

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃噩梦来袭。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        nightmares = self._find_nightmares(game_state, inv)
        if nightmares is None:
            return False
        if nightmares.instance_id in inv.threat_area:
            inv.threat_area.remove(nightmares.instance_id)
        game_state.cards_in_play.pop(nightmares.instance_id, None)
        inv.discard.append("wracked_by_nightmares_lv0")
        return True

    @staticmethod
    def _find_nightmares(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "wracked_by_nightmares_lv0":
                return inst
        return None
