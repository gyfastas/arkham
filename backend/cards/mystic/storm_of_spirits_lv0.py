"""Storm of Spirits (Level 0) — Mystic Event. (03153)
<b>攻击</b>。本次攻击不使用[combat]，改为使用[willpower]。如果成功，本次攻击
不造成标准伤害，改为对被攻击敌人所在地点的每名敌人造成2点伤害（所有额外
伤害只对被攻击的敌人造成）。如果本次攻击中揭示了[skull]、[cultist]、[tablet]、
[elder_thing]或[auto_fail]标记，对该地点的每名调查员造成1点伤害。

简化说明：
- 打出后由会话层发起战斗行动；本实现通过武装标记在下一次战斗检定中以意志
  代替战斗（同 backstab/blinding_light 惯例）。被攻击目标经
  FIGHT_ACTION_INITIATED 记录。
- 被攻击敌人的2点伤害经 bonus_damage 通道（基础1+1=2）由引擎结算；
  同地点其余敌人各直接受到2点伤害（直接累加 damage，击败清理由会话层
  _check_new_defeats 兜底，同 dynamite_blast 惯例）。
- 敌人所在地点的判定：先在各地点敌人列表中查找；交战中（在威胁区）的敌人
  视为位于其交战调查员的地点。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_BAD_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
    ChaosTokenType.AUTO_FAIL,
}


class StormOfSpirits(CardImplementation):
    card_id = "storm_of_spirits_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._target_enemy_id: str | None = None
        self._bad_token_drawn = False

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.game_state.get_investigator(ctx.investigator_id) is None:
            return
        self._armed_by = ctx.investigator_id
        self._target_enemy_id = None
        self._bad_token_drawn = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def record_target(self, ctx):
        """记录被攻击的敌人（武装后的下一次攻击）。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        self._target_enemy_id = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """本次攻击使用意志代替战斗。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, "storm_of_spirits_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_bad_token(self, ctx):
        if self._armed_by is not None and ctx.investigator_id == self._armed_by \
                and ctx.chaos_token in _BAD_TOKENS:
            self._bad_token_drawn = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def splash_damage(self, ctx):
        """成功：被攻击敌人经 bonus_damage 造成2点；同地点其余敌人各2点。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        # 被攻击敌人：标准伤害1 → 2（额外伤害仍只加给它）
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

        location = self._enemy_location(ctx)
        if location is None:
            return
        for enemy_iid in self._enemies_at_location(ctx, location):
            if enemy_iid == self._target_enemy_id:
                continue
            enemy = ctx.game_state.get_card_instance(enemy_iid)
            if enemy is not None:
                enemy.damage += 2
        ctx.extra["storm_of_spirits_splash"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        """坏标记惩罚：对该地点每名调查员造成1点伤害（无论成败）。"""
        if self._armed_by is not None and self._bad_token_drawn:
            location = self._enemy_location(ctx)
            if location is not None:
                for other in ctx.game_state.get_investigators_at_location(location):
                    other.damage += 1
                ctx.extra["storm_of_spirits_backlash"] = True
        self._armed_by = None
        self._target_enemy_id = None
        self._bad_token_drawn = False

    def _enemy_location(self, ctx) -> str | None:
        """被攻击敌人的地点：地点敌人列表优先，交战中则取攻击者地点。"""
        target = self._target_enemy_id
        if target is not None:
            for loc_id, loc in ctx.game_state.locations.items():
                if target in loc.enemies:
                    return loc_id
            for inv in ctx.game_state.investigators.values():
                if target in inv.threat_area:
                    return inv.location_id
        inv = ctx.game_state.get_investigator(self._armed_by) \
            if self._armed_by else None
        return inv.location_id if inv is not None else None

    def _enemies_at_location(self, ctx, location_id: str) -> list[str]:
        """该地点的全部敌人：未交战（地点列表）+ 与该地点调查员交战的。"""
        out: list[str] = []
        loc = ctx.game_state.get_location(location_id)
        if loc is not None:
            out.extend(loc.enemies)
        for inv in ctx.game_state.get_investigators_at_location(location_id):
            for eid in inv.threat_area:
                if eid not in out:
                    out.append(eid)
        return out
