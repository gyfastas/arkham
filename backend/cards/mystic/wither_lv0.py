"""Wither (Level 0) — Mystic Asset, Arcane slot. (05157)
[action]：攻击。本次攻击使用[willpower]代替[combat]。如果本次攻击中揭示了
[skull]、[cultist]、[tablet]或[elder_thing]符号，被攻击的敌人在本回合剩余
时间内-1战斗、-1躲避（最低减至1）。

简化说明：
- activate() 武装（无充能/横置要求）；随后由会话层发起战斗行动
  （weapon_instance_id 传本卡实例，经 FIGHT_ACTION_INITIATED 记录目标）。
- 敌人减数值按实例记录（CardData 为共享静态数据，不做持久改写）：
  战斗/躲避减值在后续对该敌人的战斗/躲避检定 ST.1 以降低难度实现
  （下限1）；lv4 的生命-1 以"降低击败阈值"实现（挂debuff时与后续每次
  伤害后按 max(1, 原生命-1) 检查击败）。
- "本回合剩余时间"：INVESTIGATOR_TURN_ENDS 时清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import defeat_enemy
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class Wither(CardImplementation):
    card_id = "wither_lv0"
    willpower_bonus = 0   # lv4: +2 意志
    health_reduction = 0  # lv4: -1 生命
    activations = [{
        "id": "fight",
        "label": "用意志攻击",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._target_enemy_id: str | None = None
        self._debuffed: set[str] = set()      # 本回合被削弱的敌人
        self._pending_enemy: str | None = None  # 即将检定所对的敌人

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """武装一次"用意志攻击"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        self._target_enemy_id = target_instance_id
        return True

    def _is_this_attack(self, ctx) -> bool:
        if not self._armed:
            return False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_fight_target(self, ctx):
        if self._armed and ctx.source == self.instance_id:
            self._target_enemy_id = ctx.enemy_id
        if ctx.enemy_id in self._debuffed:
            self._pending_enemy = ctx.enemy_id

    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def track_evade_target(self, ctx):
        if ctx.enemy_id in self._debuffed:
            self._pending_enemy = ctx.enemy_id

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reduce_enemy_stats(self, ctx):
        """对被削弱敌人的战斗/躲避检定：难度-1（即其战斗/躲避-1，下限1）。"""
        if self._pending_enemy is None or self._pending_enemy not in self._debuffed:
            return
        if ctx.skill_type not in (Skill.COMBAT, Skill.AGILITY):
            return
        if ctx.difficulty is not None and ctx.difficulty > 1:
            ctx.difficulty = ctx.difficulty - 1
            ctx.extra[f"{self.card_id}_reduced"] = self._pending_enemy

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        if ctx.source is not None and ctx.source != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(
            willpower - base_val + self.willpower_bonus,
            f"{self.card_id}_substitute",
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def apply_debuff_on_symbol(self, ctx):
        """符号标记：被攻击敌人本回合 -1战斗/-1躲避（lv4 另-1生命）。"""
        if not self._is_this_attack(ctx) or ctx.chaos_token not in _SYMBOL_TOKENS:
            return
        target_id = self._target_enemy_id
        enemy = ctx.game_state.get_card_instance(target_id) if target_id else None
        if enemy is None:
            return
        self._debuffed.add(target_id)
        ctx.extra[f"{self.card_id}_debuffed"] = target_id
        ctx.game_state.log_effect(
            f"🥀 枯萎术：【{ctx.game_state.card_name(enemy.card_id)}】"
            "本回合-1战斗-1躲避"
            + ("-1生命" if self.health_reduction else ""))
        if self.health_reduction:
            self._check_reduced_health_defeat(ctx, target_id)

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.AFTER)
    def recheck_reduced_health(self, ctx):
        """lv4：被削弱敌人后续受到伤害后，按降低后的生命阈值检查击败。"""
        if not self.health_reduction or ctx.target not in self._debuffed:
            return
        self._check_reduced_health_defeat(ctx, ctx.target)

    def _check_reduced_health_defeat(self, ctx, enemy_iid) -> None:
        enemy = ctx.game_state.get_card_instance(enemy_iid)
        if enemy is None:
            self._debuffed.discard(enemy_iid)
            return
        cd = ctx.game_state.get_card_data(enemy.card_id)
        if cd is None or not cd.enemy_health:
            return
        if enemy.damage >= max(1, cd.enemy_health - self.health_reduction):
            defeat_enemy(
                ctx.game_state, getattr(self, "_bus", None), enemy_iid,
                defeated_by=ctx.investigator_id,
            )
            self._debuffed.discard(enemy_iid)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._target_enemy_id = None
        self._pending_enemy = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire_debuffs(self, ctx):
        self._debuffed.clear()

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus
