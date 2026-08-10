"""Sixth Sense (Level 0) — Mystic Asset, Arcane slot. (05158)
[action]：调查。不使用[intellect]，改为使用[willpower]调查。如果本次检定中揭示了
[skull]、[cultist]、[tablet]或[elder_thing]符号，你可以选择与你所在地点连接的
一个已揭示地点；改为如同你在所选地点调查，而不是你所在地点（你可以使用两个
地点中任意一个的隐藏值）。

简化说明：
- activate() 武装；随后由会话层发起调查行动（武装窗口内下一次智力检定生效，
  同 rite_of_seeking 惯例；调查检定引擎不传 source）。
- 目标地点自动选择：连接范围内已揭示地点中隐藏值最低者（并列取线索最多者）。
- "使用任意一个隐藏值"：引擎检定难度在 ST.1 已锁定（本卡无法改用低隐藏值的
  事件通道），以等效的"技能值 +(原难度-目标隐藏值)"实现。
- "改为在所选地点调查"：成功的线索改从目标地点获取（本地点线索经 CLUE_DISCOVERED
  回滚）；若本地点无线索可拿（引擎未发 CLUE_DISCOVERED），在检定结束兜底时
  从目标地点补发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_SYMBOL_TOKENS = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class SixthSense(CardImplementation):
    card_id = "sixth_sense_lv0"
    willpower_bonus = 0   # lv4: +2 意志
    max_connections = 1   # lv4: 至多2条连接之外
    in_addition = False   # lv4: 两地点同时调查（目标地点线索为额外发现）
    activations = [{
        "id": "investigate",
        "label": "用意志调查",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._symbol_drawn = False
        self._clue_handled = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """武装一次"用意志调查"（无充能/横置要求）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        self._symbol_drawn = False
        self._clue_handled = False
        return True

    def _is_this_test(self, ctx) -> bool:
        if not self._armed:
            return False
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    def _choose_location(self, game_state, inv):
        """连接范围内已揭示地点：隐藏值最低优先，其次线索最多。"""
        if self.max_connections <= 1:
            candidates = []
            loc = game_state.get_location(inv.location_id)
            if loc is not None:
                for loc_id in loc.connections:
                    other = game_state.get_location(loc_id)
                    if other is not None and other.revealed:
                        candidates.append(other)
        else:
            candidates = self._bfs_revealed(game_state, inv.location_id)
        if not candidates:
            return None
        return min(candidates, key=lambda l: (l.shroud, -l.clues))

    def _bfs_revealed(self, game_state, start_id: str):
        seen = {start_id}
        frontier = [start_id]
        found = []
        for _ in range(self.max_connections):
            nxt = []
            for loc_id in frontier:
                loc = game_state.get_location(loc_id)
                if loc is None:
                    continue
                for conn_id in loc.connections:
                    if conn_id in seen:
                        continue
                    seen.add(conn_id)
                    other = game_state.get_location(conn_id)
                    if other is None:
                        continue
                    if other.revealed:
                        found.append(other)
                    nxt.append(conn_id)
            frontier = nxt
        return found

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        if ctx.skill_type != Skill.INTELLECT or not self._is_this_test(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        delta = willpower - base_val + self.willpower_bonus
        # 符号标记：可使用目标地点的隐藏值（等效技能加值）
        if self._symbol_drawn:
            target = self._choose_location(ctx.game_state, inv)
            if target is not None and ctx.difficulty is not None \
                    and target.shroud < ctx.difficulty:
                delta += ctx.difficulty - target.shroud
                ctx.extra[f"{self.card_id}_shroud_used"] = target.shroud
        ctx.modify_amount(delta, f"{self.card_id}_substitute")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def track_symbol(self, ctx):
        if self._is_this_test(ctx) and ctx.chaos_token in _SYMBOL_TOKENS:
            self._symbol_drawn = True

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def redirect_clue(self, ctx):
        """符号标记：线索改从（lv4：额外从）目标地点发现。"""
        if not self._is_this_test(ctx) or not self._symbol_drawn:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        target = self._choose_location(ctx.game_state, inv)
        if target is None:
            return
        own = ctx.game_state.get_location(inv.location_id)
        if self.in_addition:
            if target.clues > 0:
                target.clues -= 1
                inv.clues += 1
                ctx.extra[f"{self.card_id}_extra_clue"] = target.location_id
        else:
            # "而不是你所在地点"：回滚本地点的线索拾取，改从目标地点拿
            if own is not None:
                own.clues += 1
            if target.clues > 0:
                target.clues -= 1
            else:
                inv.clues = max(0, inv.clues - 1)
            ctx.extra[f"{self.card_id}_redirected"] = target.location_id
        self._clue_handled = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def cleanup(self, ctx):
        """兜底：本地点无线索（引擎未发 CLUE_DISCOVERED）时从目标地点补发。"""
        if self._armed and self._symbol_drawn and ctx.success \
                and not self._clue_handled:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None:
                target = self._choose_location(ctx.game_state, inv)
                if target is not None and target.clues > 0:
                    target.clues -= 1
                    inv.clues += 1
                    ctx.extra[f"{self.card_id}_fallback_clue"] = target.location_id
        self._armed = False
        self._symbol_drawn = False
        self._clue_handled = False
