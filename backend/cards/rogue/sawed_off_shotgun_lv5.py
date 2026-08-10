"""Sawed-Off Shotgun (Level 5) — Rogue Asset, Hand slot. (06327)
使用(2弹药)。[action]花费1弹药：攻击。这次攻击不造成其基础伤害，改为
你每成功且超过难度1点，造成1点伤害（最小1，最大6）。如果你检定失败并且
将要对另一名调查员造成伤害，这次攻击你每失败且低于难度1点，造成1点伤害
（最小1，最大6）。

简化说明：
- 弹药在发起攻击时（FIGHT_ACTION_INITIATED）扣除，无弹药取消攻击
  （同 lupara；引擎支持 FIGHT_ACTION_INITIATED 的 ctx.cancel()）。
- 成功时：伤害 = clamp(超出难度点数, 1, 6)，替换基础1点伤害
  （bonus_damage += 该值 - 1，引擎结算 base 1 + bonus）。
- 失败误伤分支：引擎的攻击失败流程不会对其他调查员造成伤害（多人误伤
  未实现，引擎缺口）；失败点数经 ctx.extra["sawed_off_fail_damage"]
  暴露给会话层处理。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


def _clamp_damage(points: int) -> int:
    return max(1, min(6, points))


class SawedOffShotgun(CardImplementation):
    card_id = "sawed_off_shotgun_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False

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
            ctx.game_state.log_effect("🔫 削短猎枪：没有弹药，攻击取消")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def variable_damage(self, ctx):
        """成功：伤害 = clamp(超过难度点数, 1, 6)，替换基础伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        damage = _clamp_damage(margin)
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + damage - 1
        ctx.extra["sawed_off_damage"] = damage
        ctx.game_state.log_effect(f"🔫 削短猎枪：超过难度{margin}点，造成{damage}点伤害")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def friendly_fire_damage(self, ctx):
        """失败：记录误伤伤害（每低于难度1点造成1伤害，1-6）供会话层结算。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        ctx.extra["sawed_off_fail_damage"] = _clamp_damage(margin)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False
