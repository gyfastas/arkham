"""Radiant Smite (Level 1) — Guardian Event. (07153)
<b>攻击</b>。这次攻击你可以不使用[combat]，改为使用[willpower]。在你发动这次攻击时，
在混乱袋中查找最多3个[bless]标记，并将其封印在此。耀灿一击上每有一个封印的[bless]
标记，这次攻击你+1技能值并造成+1伤害。如果这次攻击击败被攻击的敌人，将封印的标记
返回供应堆。否则，将其释放。

简化说明：
- 打出时即封印至多3个祝福标记（官方为"发动攻击时"，打出与攻击紧邻，简化）。
- "可以改用意志"自动取较高者（意志>战斗时才替换）。
- 攻击由会话层在打出后发起；武装期间持有者的下一次战斗检定即本次攻击。
- 目标经 ctx.extra["enemy_instance_id"] 指定，缺省取威胁区第一个敌人；
  击败判定以"武装期间持有者击败该目标"为准（未记录目标时任何击败都算）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_MAX_SEAL = 3


class RadiantSmite(CardImplementation):
    card_id = "radiant_smite_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._sealed = 0
        self._armed_for: str | None = None
        self._target: str | None = None
        self._defeated = False

    def bind_chaos_bag(self, bag) -> None:
        self._bag = bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        """打出后：封印至多3个祝福标记并武装一次攻击。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._bag is not None:
            while self._sealed < _MAX_SEAL and self._bag.seal_token(ChaosTokenType.BLESS):
                self._sealed += 1
        self._armed_for = inv.investigator_id
        self._target = ctx.extra.get("enemy_instance_id") or next(iter(inv.threat_area), None)
        self._defeated = False
        ctx.extra["radiant_smite_sealed"] = self._sealed
        ctx.game_state.log_effect(
            f"✨ 耀灿一击：封印{self._sealed}个祝福标记，本次攻击+{self._sealed}技能值/+{self._sealed}伤害")

    def _is_this_attack(self, ctx) -> bool:
        return (
            self._armed_for is not None
            and ctx.investigator_id == self._armed_for
            and ctx.skill_type == Skill.COMBAT
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def boost(self, ctx):
        """本次攻击：每个封印的祝福+1技能值；意志高于战斗时改用意志。"""
        if not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        willpower = inv.get_skill(Skill.WILLPOWER)
        combat = inv.get_skill(Skill.COMBAT)
        if willpower > combat:
            # ctx.amount 已含基础战斗值，替换差额
            ctx.modify_amount(willpower - combat, "radiant_smite_substitute")
        if self._sealed:
            ctx.modify_amount(self._sealed, "radiant_smite_sealed_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """每个封印的祝福+1伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if not self._is_this_attack(ctx):
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + self._sealed

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def mark_defeated(self, ctx):
        """武装期间目标被持有者击败：封印标记返回供应堆（不回袋）。"""
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        if self._target is not None and ctx.target != self._target:
            return
        self._defeated = True
        if self._bag is not None and self._sealed:
            for _ in range(self._sealed):
                try:
                    self._bag.sealed.remove(ChaosTokenType.BLESS)
                except ValueError:
                    break
            ctx.game_state.log_effect(
                f"✨ 耀灿一击：击败目标，{self._sealed}个封印祝福返回供应堆")
            self._sealed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        """未击败目标：释放封印的祝福（放回混乱袋）。"""
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        if not self._defeated and self._sealed and self._bag is not None:
            for _ in range(self._sealed):
                self._bag.release_token(ChaosTokenType.BLESS)
            ctx.game_state.log_effect(
                f"✨ 耀灿一击：未击败目标，释放{self._sealed}个祝福标记")
        self._sealed = 0
        self._armed_for = None
        self._target = None
        self._defeated = False
