"""Leg Injury (Level 0) — Neutral Treachery, Basic Weakness.
显现 - 将腿伤放入你的威胁区域。
腿伤可以像承受者身上的1点伤害一样被治愈（若被治愈，丢弃之）。
强制 - 在你执行移动、辞职或躲避行动后：本回合剩余时间内，
你不能执行以上类型的行动。

简化说明：
- 引擎的 MOVE/EVADE_ACTION_INITIATED 不支持取消（引擎缺口），行动封锁
  实现为 can_take_action() 供会话层在执行行动前查询。
- "像1点伤害一样被治愈"实现为公开方法 heal()（会话层在治愈效果分配
  1点伤害给本卡时调用）：丢弃本卡。
- 封锁标记在 INVESTIGATOR_TURN_ENDS 清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, TimingPriority

_BLOCKED_ACTIONS = {Action.MOVE, Action.RESIGN, Action.EVADE}


class LegInjury(CardImplementation):
    card_id = "leg_injury_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._blocked = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "leg_injury_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "leg_injury_lv0" in inv.hand:
            inv.hand.remove("leg_injury_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="leg_injury_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def block_after_action(self, ctx):
        """强制 - 移动/辞职/躲避后：本回合不能再执行这些行动。"""
        if ctx.action not in _BLOCKED_ACTIONS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_leg_injury(ctx.game_state, inv) is None:
            return
        self._blocked = True
        ctx.game_state.log_effect(
            "🦵 腿伤：本回合不能再执行移动/辞职/躲避行动"
        )

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._blocked = False

    def can_take_action(self, game_state, investigator_id, action) -> bool:
        """会话层查询：指定行动当前是否可执行。"""
        if not self._blocked or action not in _BLOCKED_ACTIONS:
            return True
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        return self._find_leg_injury(game_state, inv) is None

    def heal(self, game_state, investigator_id) -> bool:
        """作为1点伤害被治愈：丢弃腿伤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_leg_injury(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("leg_injury_lv0")
        game_state.log_effect("🦵 腿伤：被治愈，丢弃")
        return True

    @staticmethod
    def _find_leg_injury(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "leg_injury_lv0":
                return inst
        return None
