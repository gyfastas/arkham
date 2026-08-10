"""Stupor (Level 0) — Neutral Treachery, Basic Weakness. (08133)
显现 - 将麻木放置入你的威胁区域。
麻木可以被视为你的1点恐惧来治疗（若被治疗，丢弃它）。
强制 - 在你进行谈判、抽牌或调查行动后：本回合剩余时间内你不能再进行
这些类型的行动。

简化说明：同 panic_lv0（行动类型封锁由 can_take_action() 供会话层查询）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, TimingPriority

BLOCKED_ACTIONS = {Action.PARLEY, Action.DRAW, Action.INVESTIGATE}


class Stupor(CardImplementation):
    card_id = "stupor_lv0"
    blocked_actions = BLOCKED_ACTIONS

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._blocked: set[Action] = set()

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "stupor_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "stupor_lv0" in inv.hand:
            inv.hand.remove("stupor_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="stupor_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def block_action_types(self, ctx):
        """进行谈判/抽牌/调查行动后：本回合封锁这些行动类型。"""
        if ctx.action not in BLOCKED_ACTIONS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._find_stupor(ctx.game_state, inv) is None:
            return
        self._blocked.update(BLOCKED_ACTIONS)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_on_turn_end(self, ctx):
        self._blocked.clear()

    def can_take_action(self, game_state, investigator_id, action: Action) -> bool:
        """会话层查询：该行动当前是否被麻木封锁。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self._find_stupor(game_state, inv) is None:
            return True
        return action not in self._blocked

    def heal(self, game_state, investigator_id) -> bool:
        """将本卡视为1点恐惧治疗：丢弃麻木。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_stupor(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("stupor_lv0")
        return True

    @staticmethod
    def _find_stupor(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "stupor_lv0":
                return inst
        return None
