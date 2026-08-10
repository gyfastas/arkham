"""Shroud of Shadows (Level 0) — Mystic Asset, Arcane slot. (07119)
使用(3充能)。
[action]花费1充能：躲避。本次躲避使用[willpower]代替[agility]。如果成功且被躲避
的敌人非[[精英]]，你可以将该敌人移动到一个连接地点。如果本次躲避中揭示了[curse]
标记，你可以移动到一个连接地点，或在本卡上放置1充能。

简化说明：
- activate() 花费1充能并武装；随后由会话层发起躲避行动（武装窗口内下一次
  敏捷检定生效，同 blinding_light 惯例；躲避检定引擎不传 source）。
- "将敌人移动到连接地点"：自动选择当前地点的第一个连接地点（无选择 UI）。
- curse 标记奖励二选一（自己移动 / 放置充能）简化为自动放置1充能。
- 数据 JSON 中 uses 键为 "chargess"（上游笔误），经 seeker._uses 兼容读取。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_key, uses_spend
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)
from backend.scenarios.official_core import is_elite_enemy


class ShroudOfShadows(CardImplementation):
    card_id = "shroud_of_shadows_lv0"
    willpower_bonus = 0      # lv4: +2 意志
    charge_per_curse = False  # lv4: 每个 curse 标记1充能（lv0 任意 curse 1充能）
    activations = [{
        "id": "evade",
        "label": "花1充能：用意志躲避",
        "method": "activate",
        "actions": 1,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._curses = 0

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None) -> bool:
        """花费1充能：武装一次"用意志躲避"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or not uses_spend(inst, "charges"):
            return False
        self._armed = True
        self._curses = 0
        return True

    def _is_this_evasion(self, ctx) -> bool:
        if not self._armed:
            return False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type != Skill.AGILITY or not self._is_this_evasion(ctx):
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
    def track_curse(self, ctx):
        if self._is_this_evasion(ctx) and ctx.chaos_token == ChaosTokenType.CURSE:
            self._curses += 1

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def move_evaded_enemy(self, ctx):
        """成功且敌人非精英：自动移动到第一个连接地点。"""
        if not self._is_this_evasion(ctx):
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None:
            return
        cd = ctx.game_state.get_card_data(enemy.card_id)
        if cd is not None and is_elite_enemy(cd):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        loc = ctx.game_state.get_location(inv.location_id) if inv else None
        if loc is None or not loc.connections:
            return
        dest = ctx.game_state.get_location(loc.connections[0])
        if dest is None or ctx.enemy_id not in loc.enemies:
            return
        loc.enemies.remove(ctx.enemy_id)
        dest.enemies.append(ctx.enemy_id)
        ctx.extra[f"{self.card_id}_moved_enemy"] = dest.location_id
        ctx.game_state.log_effect(
            f"🌫 暗影遁形：将【{ctx.game_state.card_name(enemy.card_id)}】"
            f"移动到【{ctx.game_state.card_name(dest.location_id)}】")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_curse_reward(self, ctx):
        """curse 奖励：自动选择放置充能（lv0 任一 curse 1充；lv4 每个1充）。"""
        if self._armed and self._curses > 0:
            inst = ctx.game_state.get_card_instance(self.instance_id)
            if inst is not None:
                n = self._curses if self.charge_per_curse else 1
                key = uses_key(inst, "charges")
                inst.uses[key] = uses_count(inst, "charges") + n
                ctx.extra[f"{self.card_id}_charges_gained"] = n
                ctx.game_state.log_effect(f"🌫 暗影遁形：放置{n}充能")
        self._armed = False
        self._curses = 0
