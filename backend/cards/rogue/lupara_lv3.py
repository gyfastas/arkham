"""Lupara (Level 3) — Rogue Asset, Hand slot.
使用(2弹药)。打出短管猎枪不会引起趁乱攻击。
[行动]花费1弹药：攻击。本次攻击你+1战斗并造成+1伤害。
如果短管猎枪本回合中入场，本次攻击你额外+1战斗并造成额外+1伤害。

简化说明：
- 弹药在发起攻击时（FIGHT_ACTION_INITIATED）扣除（official 时机）；
  无弹药时取消攻击（引擎支持 FIGHT_ACTION_INITIATED 的 ctx.cancel()）。
- "打出不引起趁乱攻击"：CARD_ENTERS_PLAY 到紧随的 AoO 结算之间取消
  一次趁乱攻击（覆盖打出动作触发的 AoO 窗口；ACTION_PERFORMED 后失效）。
- "本回合中入场"标记在任意调查员回合结束时清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Lupara(CardImplementation):
    card_id = "lupara_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._entered_this_turn = False
        self._just_entered = False  # 打出动作的 AoO 窗口
        self._attack_paid = False

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def mark_entered(self, ctx):
        if ctx.target != self.instance_id:
            return
        self._entered_this_turn = True
        self._just_entered = True

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo_from_playing(self, ctx):
        """打出短管猎枪不会引起趁乱攻击。"""
        if not self._just_entered:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.cancel()
        self._just_entered = False
        ctx.game_state.log_effect("🔫 短管猎枪：打出不引起趁乱攻击")

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def close_aoo_window(self, ctx):
        self._just_entered = False

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_entered_flag(self, ctx):
        self._entered_this_turn = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """花费1弹药：攻击。无弹药时攻击被取消（不花费行动）。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            self._attack_paid = False
            ctx.cancel()
            ctx.game_state.log_effect("🔫 短管猎枪：没有弹药，攻击取消")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+1战斗；本回合入场则额外+1。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = 2 if self._entered_this_turn else 1
        ctx.modify_amount(bonus, "lupara_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage(self, ctx):
        """+1伤害；本回合入场则额外+1。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = 2 if self._entered_this_turn else 1
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + bonus

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_state(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False
