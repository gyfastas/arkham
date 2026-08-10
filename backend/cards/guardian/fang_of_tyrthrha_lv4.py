"""Fang of Tyr'thrha (Level 4) — Guardian Event. (08029)
攻击。选择任意已揭示地点的一名敌人作为本次攻击的目标。在结算本次攻击前，
你可以移动到该敌人所在地点。本次攻击你将敏捷加到你的战斗上。
本次攻击造成+3伤害。

简化说明：
- 目标自动选择：优先与你交战的敌人，其次任意已揭示地点的敌人（会话层
  PLAY 通道不传目标；可经 ctx.extra["fang_target"] 指定实例）。
- "可以移动到敌人所在地点"简化为自动移动（目标不在你所在地点时；
  本移动为卡牌效果而非移动行动，不引起趁乱攻击）。与你交战的敌人
  随你移动（威胁区跟随调查员，引擎天然如此）。
- 打出后由会话层发起战斗行动（同 backstab 惯例）；本实现武装持有者
  下一次战斗检定：敏捷加到战斗上，成功时 +3 伤害。
- 事件实现实例存活至 ROUND_ENDS（引擎事件生命周期），武装仅限一次检定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class FangOfTyrthrha(CardImplementation):
    card_id = "fang_of_tyrthrha_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def pick_target_and_move(self, ctx):
        """打出时：选择目标敌人并可移动到其所在地点，武装强化攻击。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target_iid = ctx.extra.get("fang_target")
        if target_iid is None:
            target_iid = self._pick_target(ctx.game_state, inv)
        if target_iid is None:
            ctx.extra["fang_fizzle"] = True
            ctx.game_state.log_effect("🐍 提尔斯哈之牙：没有可选择的敌人，效果不结算")
            return

        # 自动移动到目标所在地点（若不同）
        target_loc_id = self._enemy_location(ctx.game_state, target_iid)
        if target_loc_id is not None and target_loc_id != inv.location_id:
            inv.location_id = target_loc_id
            ctx.extra["fang_moved_to"] = target_loc_id
            ctx.game_state.log_effect(f"🐍 提尔斯哈之牙：移动到 {target_loc_id}")

        self._armed_for = inv.investigator_id
        ctx.extra["fang_target"] = target_iid
        ctx.game_state.log_effect("🐍 提尔斯哈之牙：攻击目标已锁定（+敏捷，+3伤害）")

    @staticmethod
    def _pick_target(game_state, inv) -> str | None:
        """自动选择：优先与你交战的敌人，其次任意已揭示地点的敌人。"""
        if inv.threat_area:
            return inv.threat_area[0]
        for loc in game_state.locations.values():
            if loc.revealed and loc.enemies:
                return loc.enemies[0]
        return None

    @staticmethod
    def _enemy_location(game_state, enemy_iid: str) -> str | None:
        for other in game_state.investigators.values():
            if enemy_iid in other.threat_area:
                return other.location_id
        for loc in game_state.locations.values():
            if enemy_iid in loc.enemies:
                return loc.location_id
        return None

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_agility(self, ctx):
        """武装的攻击：将敏捷加到你的战斗上。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        agility = inv.get_skill(Skill.AGILITY)
        if agility:
            ctx.modify_amount(agility, "fang_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """武装的攻击成功：+3伤害。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 3

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_for = None
