"""Prophesiae Profana (Level 5) — Seeker Asset, Hand slot. (08045)
只要你没位于座标点，你获得+1[intellect]和+1[agility]，并且你可以忽略
趁乱攻击。
[反应]在亵渎预言入场后：选择一个已揭示地点。该地点为"座标点"，直到
亵渎预言离场为止。
[行动]：移动任一位调查员到座标点。

简化说明：
- 座标点的选择无 UI：CARD_ENTERS_PLAY 时自动取持有者当前地点（已揭示
  时），否则第一个已揭示地点；公开方法 set_locus() 供会话层改选
  （含入场前预置，入场时优先采用）；记录在 scenario.vars 便于序列化；
- 忽略趁乱攻击经 ATTACK_OF_OPPORTUNITY 取消实现（仅持有者、且不位于
  座标点时）；
- [行动]移动为 activate()（activations 声明），target_investigator_id
  缺省为自己；移动引发的交战/地点效果由会话层结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_VAR = "prophesiae_profana_locus"


class ProphesiaeProfana(CardImplementation):
    card_id = "prophesiae_profana_lv5"
    activations = [{
        "id": "move_to_locus",
        "label": "[行动]移动任一调查员到座标点",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_locus: str | None = None  # 入场前预置的座标点

    @staticmethod
    def _locus(game_state) -> str | None:
        return game_state.scenario.vars.get(_VAR)

    def set_locus(self, game_state, location_id: str) -> bool:
        """选择/改选一个已揭示地点为座标点。"""
        loc = game_state.get_location(location_id)
        if loc is None or not loc.revealed:
            return False
        game_state.scenario.vars[_VAR] = location_id
        return True

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def choose_locus(self, ctx):
        """入场后：确定座标点（预置 > 当前地点 > 第一个已揭示地点）。"""
        if ctx.target != self.instance_id:
            return
        if self._pending_locus is not None:
            loc = ctx.game_state.get_location(self._pending_locus)
            if loc is not None and loc.revealed:
                ctx.game_state.scenario.vars[_VAR] = self._pending_locus
                self._pending_locus = None
                return
            self._pending_locus = None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            current = ctx.game_state.get_location(inv.location_id)
            if current is not None and current.revealed:
                ctx.game_state.scenario.vars[_VAR] = current.location_id
                return
        for loc in ctx.game_state.locations.values():
            if loc.revealed:
                ctx.game_state.scenario.vars[_VAR] = loc.location_id
                return

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def clear_locus(self, ctx):
        if ctx.target != self.instance_id:
            return
        ctx.game_state.scenario.vars.pop(_VAR, None)

    def _off_locus(self, ctx, inv) -> bool:
        locus = self._locus(ctx.game_state)
        return locus is not None and inv.location_id != locus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """不位于座标点时：+1[intellect]、+1[agility]。"""
        if ctx.skill_type not in (Skill.INTELLECT, Skill.AGILITY):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if not self._off_locus(ctx, inv):
            return
        ctx.modify_amount(1, "prophesiae_profana_bonus")

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def ignore_aoo(self, ctx):
        """不位于座标点时：忽略趁乱攻击。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if not self._off_locus(ctx, inv):
            return
        ctx.cancel()
        ctx.extra["prophesiae_profana_aoo_ignored"] = True
        ctx.game_state.log_effect("🗺️ 亵渎预言：忽略趁乱攻击")

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        """[行动]：移动任一位调查员到座标点。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        locus = self._locus(game_state)
        if locus is None or game_state.get_location(locus) is None:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None:
            return False
        target.location_id = locus
        game_state.log_effect(
            f"🗺️ 亵渎预言：{target.investigator_id}移动到座标点"
            f"【{game_state.card_name(locus)}】")
        return True
