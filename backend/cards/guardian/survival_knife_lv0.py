"""Survival Knife (Level 0) — Guardian Asset, Hand slot. (04017)
[action]：<b>攻击</b>。这次攻击中你+1[combat]。
[reaction]在一个敌人在敌军阶段攻击你并对你造成伤害后，消耗求生匕首：
<b>攻击</b>。这次攻击将刚刚发动攻击的敌人作为目标。这次攻击中你+2[combat]
并造成+1伤害。

简化说明：
- 普通攻击为启动能力（activate() 武装，动作费用由会话层扣除）；修正仅对
  以本卡发起的攻击生效（ctx.source == 本卡实例）。
- 反击为自动触发：敌军阶段你被敌人攻击并分配伤害后（DAMAGE_ASSIGNED，
  来源为敌人实例），自动消耗本卡并武装反击；随后的反击由会话层以本卡为
  武器发起战斗行动（反击记录的目标供会话层作为攻击目标）。
- 反击判定以"敌军阶段 + 事件来源为敌人"近似"敌人攻击对你造成伤害"
  （伤害被盟友分担或取消时也会触发，与官方"对你造成伤害"略有差异，注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, GameEvent, Phase, Skill, TimingPriority,
)


class SurvivalKnife(CardImplementation):
    card_id = "survival_knife_lv0"
    activations = [{
        "id": "fight",
        "label": "攻击：+1战斗",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False            # 普通攻击（+1战斗）
        self._retaliate_for: str | None = None   # 反击武装的调查员
        self._retaliate_target: str | None = None  # 反击目标敌人

    # ---- 普通攻击 ----

    def activate(self, game_state, investigator_id: str,
                 enemy_instance_id: str | None = None) -> bool:
        """[action] 武装普通攻击：+1战斗。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        return True

    # ---- 反击 ----

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def arm_retaliation(self, ctx):
        """敌军阶段敌人攻击对你造成伤害后：消耗本卡，武装反击。"""
        if ctx.game_state.scenario.current_phase != Phase.ENEMY:
            return
        if (ctx.amount or 0) <= 0:
            return
        attacker = ctx.game_state.get_card_instance(ctx.source) if ctx.source else None
        attacker_data = (
            ctx.game_state.get_card_data(attacker.card_id) if attacker else None
        )
        if attacker is None or attacker_data is None:
            return
        if attacker_data.type != CardType.ENEMY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return
        if inst.exhausted:
            return

        inst.exhausted = True
        self._retaliate_for = inv.investigator_id
        self._retaliate_target = ctx.source
        ctx.game_state.log_effect(
            f"🔪 求生匕首：消耗，对【{ctx.game_state.card_name(attacker.card_id)}】"
            "发起反击（+2战斗/+1伤害）")

    @property
    def retaliate_target(self) -> str | None:
        """会话层读取：反击应指向的敌人实例 id。"""
        return self._retaliate_target

    # ---- 修正结算 ----

    def _is_this_attack(self, ctx) -> bool:
        return (
            ctx.skill_type == Skill.COMBAT
            and ctx.source == self.instance_id
            and (self._armed or self._retaliate_for == ctx.investigator_id)
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if not self._is_this_attack(ctx):
            return
        bonus = 2 if self._retaliate_for == ctx.investigator_id else 1
        ctx.modify_amount(bonus, "survival_knife_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """反击成功：+1伤害（普通攻击无加伤）。"""
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        if self._retaliate_for != ctx.investigator_id:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        if ctx.investigator_id == self._retaliate_for:
            self._retaliate_for = None
            self._retaliate_target = None
