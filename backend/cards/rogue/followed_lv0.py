"""Followed (Level 0) — Rogue Event. (06114)
调查。选择你所在地点的一名敌人。本次调查中，该敌人每有1点伤害你+1智力
（至多+5）。若你成功，在该地点额外发现1个线索。本次行动不引发所选敌人
的趁乱攻击。

简化说明：
- "选择一名敌人"无选择 UI：自动选择你所在地点伤害最多的敌人（最有利；
  交战敌人优先于地点未交战敌人无差异，均按伤害排序取第一）。
- 打出后武装：随后由会话层发起调查行动；+智力经 SKILL_VALUE_DETERMINED，
  额外线索在调查成功时直接结算，所选敌人的趁乱攻击经
  ATTACK_OF_OPPORTUNITY 取消。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MAX_BONUS = 5


class Followed(CardImplementation):
    card_id = "followed_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._enemy_id: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "followed_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._armed = True
        self._enemy_id = self._choose_enemy(ctx.game_state, inv)
        ctx.extra["followed_enemy"] = self._enemy_id

    def _choose_enemy(self, game_state, inv) -> str | None:
        """自动选择你所在地点伤害最多的敌人（简化：官方为玩家选择）。"""
        candidates: list = []
        seen = set()
        loc = game_state.get_location(inv.location_id)
        pool = list(inv.threat_area) + (list(loc.enemies) if loc else [])
        for eid in pool:
            if eid in seen:
                continue
            seen.add(eid)
            inst = game_state.get_card_instance(eid)
            if inst is not None:
                candidates.append(inst)
        if not candidates:
            return None
        return max(candidates, key=lambda e: e.damage).instance_id

    def _chosen_damage(self, game_state) -> int:
        inst = game_state.get_card_instance(self._enemy_id) if self._enemy_id else None
        return inst.damage if inst is not None else 0

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def intellect_bonus(self, ctx):
        """所选敌人每1点伤害+1智力（至多+5）。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonus = min(_MAX_BONUS, self._chosen_damage(ctx.game_state))
        if bonus > 0:
            ctx.modify_amount(bonus, "followed_intellect_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def extra_clue(self, ctx):
        """调查成功：在该地点额外发现1个线索。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra["followed_extra_clue"] = True
            ctx.game_state.log_effect("👣 尾随：额外发现1个线索")

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def no_aoo_from_chosen(self, ctx):
        """本次行动不引发所选敌人的趁乱攻击。"""
        if not self._armed or self._enemy_id is None:
            return
        if ctx.enemy_id != self._enemy_id:
            return
        ctx.cancel()
        ctx.extra["followed_aoo_cancelled"] = True

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_after_investigate(self, ctx):
        """调查行动完成（含趁乱攻击结算）后解除武装。引擎在行动的技能检定
        结束后才结算趁乱攻击（actions.perform_action 先跑检定再发
        ATTACK_OF_OPPORTUNITY），故武装不能在 SKILL_TEST_ENDS 清除。"""
        from backend.models.enums import Action
        if ctx.action == Action.INVESTIGATE:
            self._armed = False
            self._enemy_id = None

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        self._armed = False
        self._enemy_id = None
