"""Suggestion (Level 4) — Rogue Asset, Arcane slot.
使用(3充能)。
[行动]消耗建议：躲避。本次躲避尝试将你的意志值加入你的技能值。
若你未成功并超过难度至少2点，从建议上移除1充能。
[反应]在一个非[[精英]]敌人将要攻击你时，花费1充能：取消该次攻击。

简化说明：
- activate() 消耗本卡并武装；随后由会话层发起躲避行动
  （lockpicks 同模式；若先做了其他检定，武装在 SKILL_TEST_ENDS 时清除）。
- 官方卡面无"充能耗尽则弃置"条款：耗尽后保留在场上。
- 取消攻击的反应简化为自动花费充能触发（官方为玩家选择时机）；
  敌人阶段攻击（ENEMY_ATTACKS）与趁乱攻击（ATTACK_OF_OPPORTUNITY，
  官方属攻击的一种）都可取消。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Suggestion(CardImplementation):
    card_id = "suggestion_lv4"
    activations = [{
        "id": "evade",
        "label": "消耗：躲避（意志加到技能值；未超2移除1充能）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_willpower(self, ctx):
        """躲避：将意志值加到技能值上。"""
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(inv.get_skill(Skill.WILLPOWER), "suggestion_willpower")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def remove_charge_on_low_margin(self, ctx):
        """成功但未超出难度至少2点：移除1充能。"""
        if not self._armed:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 2:
            self._remove_charge(ctx)

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def remove_charge_on_fail(self, ctx):
        """检定失败：移除1充能。"""
        if not self._armed:
            return
        self._remove_charge(ctx)

    def _remove_charge(self, ctx) -> None:
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inst.uses["charges"] = max(0, inst.uses.get("charges", 0) - 1)
        ctx.extra["suggestion_charge_removed"] = True

    def _try_cancel_attack(self, ctx) -> None:
        """[反应]非精英敌人将要攻击你：花费1充能取消（自动触发简化）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id) if ctx.enemy_id else None
        if enemy is None:
            return
        enemy_data = ctx.game_state.get_card_data(enemy.card_id)
        if enemy_data is None or "elite" in (enemy_data.keywords or []):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) < 1:
            return
        inst.uses["charges"] -= 1
        ctx.cancel()
        ctx.extra["suggestion_attack_cancelled"] = ctx.enemy_id
        ctx.game_state.log_effect("💬 建议：花费1充能，取消敌人攻击")

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_enemy_attack(self, ctx):
        self._try_cancel_attack(ctx)

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        self._try_cancel_attack(ctx)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
