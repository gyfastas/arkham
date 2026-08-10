"""Armageddon (Level 0) — Mystic Asset, Arcane slot. (07117)
使用(3充能)。[action]花费1充能：攻击。本次攻击使用[willpower]代替[combat]，
并造成+1伤害。如果本次攻击中揭示了[curse]标记，你可以对你所在地点的一名敌人
造成1点伤害，或在哈米吉多顿上放置1充能。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起战斗行动（weapon_instance_id
  传本卡实例），检定时以意志代替战斗（同 shrivelling 惯例）。
- [curse]标记奖励二选一：自动优先对本次攻击目标（在你地点的敌人）造成1点伤害；
  无目标时改为放置1充能。会话层可将 curse_effect 设为 "charge" 强制放充能，
  或用 curse_target_instance_id 指定伤害目标。
- 伤害直接累加 enemy.damage（与 storm_of_spirits 溅射一致；击败清理由会话层兜底）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class Armageddon(CardImplementation):
    card_id = "armageddon_lv0"
    bonus_willpower = 0  # lv4 覆盖：+2
    activations = [{
        "id": "fight",
        "label": "花1充能：用意志攻击，+1伤害",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._target_enemy_id: str | None = None
        # 会话层可选："damage"（默认）或 "charge"
        self.curse_effect = "damage"
        self.curse_target_instance_id: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """花费1充能：武装一次"用意志攻击"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        self._armed = True
        self._target_enemy_id = None
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def record_target(self, ctx):
        if self._armed and ctx.source == self.instance_id:
            self._target_enemy_id = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(
            willpower - base_val + self.bonus_willpower,
            f"{self.card_id}_substitute",
        )

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """攻击成功：+1伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if not self._is_this_attack(ctx):
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def curse_bonus(self, ctx):
        """揭示[curse]：对地点一名敌人造成1伤害，或在本卡上放置1充能。"""
        if not self._is_this_attack(ctx) or ctx.chaos_token != ChaosTokenType.CURSE:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target = None
        if self.curse_effect == "damage":
            target = self._find_damage_target(ctx, inv)
        if target is not None:
            target.damage += 1
            ctx.extra[f"{self.card_id}_curse_damage"] = target.instance_id
            ctx.game_state.log_effect(
                f"🌙 哈米吉多顿：[curse]奖励，对【{ctx.game_state.card_name(target.card_id)}】造成1伤害")
        else:
            inst = ctx.game_state.get_card_instance(self.instance_id)
            if inst is not None:
                inst.uses["charges"] = inst.uses.get("charges", 0) + 1
                ctx.extra[f"{self.card_id}_curse_charge"] = True
                ctx.game_state.log_effect("🌙 哈米吉多顿：[curse]奖励，放置1充能")

    def _find_damage_target(self, ctx, inv):
        """你所在地点的敌人：优先指定目标/攻击目标，否则地点上第一个敌人。"""
        candidates = []
        if self.curse_target_instance_id:
            candidates.append(self.curse_target_instance_id)
        if self._target_enemy_id:
            candidates.append(self._target_enemy_id)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            candidates.extend(loc.enemies)
        for other in ctx.game_state.get_investigators_at_location(inv.location_id):
            candidates.extend(other.threat_area)
        for iid in candidates:
            enemy = ctx.game_state.get_card_instance(iid)
            if enemy is not None:
                return enemy
        return None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._target_enemy_id = None
