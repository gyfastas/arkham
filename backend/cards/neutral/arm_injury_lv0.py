"""Arm Injury (Level 0) — Neutral Treachery, Basic Weakness.
显现：放置入你的威胁区域。
手臂伤势可以像你身上的1点伤害一样被治疗（若被治疗，丢弃它）。
强制 - 在你进行战斗或启动行动后：本回合剩余时间内，你不能再进行
这些类型的行动。

简化说明：
- "不能再进行战斗/启动行动"：引擎的行动分发不咨询卡牌（引擎缺口），
  本实现跟踪封锁状态并提供 can_take_action() 供会话层过滤；
  ACTION_PERFORMED 在行动结算后发出，回合开始（INVESTIGATOR_TURN_BEGINS）
  重置封锁。
- "启动行动"以 Action.ACTIVATE / Action.TOME_ACTIVATE 近似。
- 治疗经 heal() 公开方法由会话层在治疗结算时调用（治疗不经过事件总线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, TimingPriority

_BLOCKED_ACTIONS = {Action.FIGHT, Action.ACTIVATE, Action.TOME_ACTIVATE}


class ArmInjury(CardImplementation):
    card_id = "arm_injury_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._blocked = False  # 本回合已触发封锁

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "arm_injury_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "arm_injury_lv0" in inv.hand:
            inv.hand.remove("arm_injury_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="arm_injury_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def reset_block(self, ctx):
        self._blocked = False

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def block_after_fight_or_activate(self, ctx):
        """进行战斗或启动行动后：本回合不能再进行这些类型的行动。"""
        if ctx.action not in _BLOCKED_ACTIONS:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_injury(ctx.game_state, inv) is None:
            return
        self._blocked = True
        ctx.extra["arm_injury_blocked"] = True
        ctx.game_state.log_effect(
            "🦴 手臂伤势：本回合不能再进行战斗/启动行动")

    def can_take_action(self, game_state, investigator_id, action) -> bool:
        """会话层过滤用：该行动类型当前是否被手臂伤势封锁。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self._find_injury(game_state, inv) is None:
            return True
        if self._blocked and action in _BLOCKED_ACTIONS:
            return False
        return True

    def heal(self, game_state, investigator_id) -> bool:
        """被当作1点伤害治疗时：丢弃手臂伤势。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_injury(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("arm_injury_lv0")
        return True

    @staticmethod
    def _find_injury(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "arm_injury_lv0":
                return inst
        return None
