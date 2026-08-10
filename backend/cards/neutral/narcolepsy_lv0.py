"""Narcolepsy (Level 0) — Neutral Treachery, Basic Weakness.
仅多人游戏。
显现 - 将嗜睡症放入你的威胁区域。
你不能执行行动、触发能力或打出卡牌。
[action]："醒来！"丢弃嗜睡症。
强制 - 在你受到伤害或恐惧后：丢弃嗜睡症。

简化说明：
- "不能执行行动/触发能力/打出卡牌"：引擎行动通道无通用禁止钩子
  （引擎缺口），实现为 can_take_action() 供会话层查询。
- 强制效果挂在 DAMAGE_ASSIGNED / HORROR_ASSIGNED（引擎常规伤害通道；
  直接修改 inv.damage/horror 的"直接伤害"不经事件，不触发，注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Narcolepsy(CardImplementation):
    card_id = "narcolepsy_lv0"
    activations = [{
        "id": "wake_up",
        "label": "[行动] \"醒来！\"丢弃嗜睡症",
        "method": "activate_wake_up",
        "actions": 1,
    }]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "narcolepsy_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "narcolepsy_lv0" in inv.hand:
            inv.hand.remove("narcolepsy_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="narcolepsy_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def discard_on_damage(self, ctx):
        self._maybe_discard(ctx)

    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.AFTER)
    def discard_on_horror(self, ctx):
        self._maybe_discard(ctx)

    def _maybe_discard(self, ctx):
        """强制 - 在你受到伤害或恐惧后：丢弃嗜睡症。"""
        if (ctx.amount or 0) < 1:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_narcolepsy(ctx.game_state, inv) is None:
            return
        self._discard(ctx.game_state, inv)
        ctx.game_state.log_effect("😴 嗜睡症：受到伤害/恐惧，丢弃")

    def can_take_action(self, game_state, investigator_id) -> bool:
        """会话层查询：嗜睡症在场时不能执行行动/触发能力/打出卡牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        return self._find_narcolepsy(game_state, inv) is None

    def activate_wake_up(self, game_state, investigator_id) -> bool:
        """[action] "醒来！"丢弃嗜睡症。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        if self._find_narcolepsy(game_state, inv) is None:
            return False
        self._discard(game_state, inv)
        return True

    @staticmethod
    def _discard(game_state, inv) -> None:
        inst = Narcolepsy._find_narcolepsy(game_state, inv)
        if inst is None:
            return
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("narcolepsy_lv0")

    @staticmethod
    def _find_narcolepsy(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "narcolepsy_lv0":
                return inst
        return None
