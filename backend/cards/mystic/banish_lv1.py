"""Banish (Level 1) — Mystic Event. (05113)
躲避。仅可对非[[精英]]敌人使用。这次躲避尝试使用[willpower]代替[agility]。
如果你成功，将刚刚躲避的敌人移动到场上任意一个地点。如果你成功，且这次
躲避尝试期间揭示[skull]、[cultist]、[tablet]或[elder_thing]符号，该敌人在
下一个补给阶段中不准备。

简化说明：
- 打出后由会话层发起躲避行动；本实现通过 active_effects 武装，
  在下一次敏捷（躲避）检定中以意志代替敏捷（同 blinding_light 惯例）。
- "仅非精英"：EVADE_ACTION_INITIATED 时校验目标，精英目标不生效
  （引擎 _evade 不响应事件取消，无法拦截行动本身——引擎缺口）。
- 移动目标地点自动选择：按地点 id 排序的第一个其他地点（无选择 UI；
  无其他地点时留在原地）。
- "下一个补给阶段不准备"：补给阶段内拦截 CARD_READIED 重新横置
  （同 bind_monster 惯例），补给结束后清除标记。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)
from backend.scenarios.official_core import is_elite_enemy

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class Banish(CardImplementation):
    card_id = "banish_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._eligible = True
        self._bad_token_drawn = False
        self._no_ready_enemy: str | None = None
        self._in_upkeep = False

    def _is_armed(self, game_state, investigator_id) -> bool:
        if self._armed_by != investigator_id:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return bool(getattr(inv, "active_effects", {}).get(self.card_id))

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[self.card_id] = True
        self._armed_by = ctx.investigator_id
        self._eligible = True
        self._bad_token_drawn = False

    @on_event(GameEvent.EVADE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def check_elite(self, ctx):
        """仅非精英敌人有效；精英目标不享受本卡任何效果。"""
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        cd = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if cd is not None and is_elite_enemy(cd):
            self._eligible = False
            ctx.game_state.log_effect("🚫 驱除：目标为精英敌人，本卡无效")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """躲避检定：用意志代替敏捷。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        if not self._eligible:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, "banish_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bad_token(self, ctx):
        if self._is_armed(ctx.game_state, ctx.investigator_id) \
                and ctx.chaos_token in _BAD_TOKENS:
            self._bad_token_drawn = True

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def move_evaded_enemy(self, ctx):
        """成功：将刚躲避的敌人移动到任意地点；坏符号则下补给不准备。"""
        if not self._is_armed(ctx.game_state, ctx.investigator_id):
            return
        if not self._eligible:
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        current = inv.location_id if inv is not None else None

        # 移动到任意地点（简化：按 id 排序的第一个其他地点）
        destination = None
        for loc_id in sorted(ctx.game_state.locations):
            if loc_id != current:
                destination = loc_id
                break
        if destination is not None:
            for loc in ctx.game_state.locations.values():
                if ctx.enemy_id in loc.enemies:
                    loc.enemies.remove(ctx.enemy_id)
            ctx.game_state.locations[destination].enemies.append(ctx.enemy_id)
            ctx.extra["banish_moved_to"] = destination
            ctx.game_state.log_effect(
                f"🌀 驱除：敌人被放逐到【{ctx.game_state.card_name(destination)}】")

        if self._bad_token_drawn:
            self._no_ready_enemy = ctx.enemy_id
            ctx.extra["banish_no_ready"] = True

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.AFTER)
    def upkeep_begins(self, ctx):
        self._in_upkeep = True

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def prevent_ready(self, ctx):
        """下一个补给阶段：被驱除的敌人不准备。"""
        if not self._in_upkeep or self._no_ready_enemy is None:
            return
        if ctx.target != self._no_ready_enemy:
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is not None:
            enemy.exhausted = True
            ctx.extra["banish_prevented_ready"] = True
        self._no_ready_enemy = None  # 仅下一个补给阶段

    @on_event(GameEvent.UPKEEP_PHASE_ENDS, priority=TimingPriority.AFTER)
    def upkeep_ends(self, ctx):
        self._in_upkeep = False
        self._no_ready_enemy = None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        for inv in ctx.game_state.investigators.values():
            getattr(inv, "active_effects", {}).pop(self.card_id, None)
        self._armed_by = None
        self._eligible = True
        self._bad_token_drawn = False
