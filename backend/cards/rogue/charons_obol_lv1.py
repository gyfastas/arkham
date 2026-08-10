"""Charon's Obol (Level 1) — Rogue Asset.
永久。卓越。
在冒险结局中获得经验时，如果你该次冒险中没有被击败，你获得额外2点经验。
如果你该次冒险中被击败，你阵亡。

简化说明：
- 经验结算与"阵亡"属于战役层（战役记录/牌组成长），单局引擎无经验系统
  （引擎缺口）。本卡实现单局内可观测的部分：记录持有者在本次冒险中
  是否被击败（scenario.vars["charons_obol"]），并提供公开方法
  apply_scenario_xp() 供战役层在冒险结局调用：
  未被击败 → 经验+2；被击败 → 标记 killed。
- "永久"（开局入场）与"卓越"（牌组限制，每局限带1张）为牌组/战役规则，
  由会话层/牌组构建负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_VARS_KEY = "charons_obol"


class CharonsObol(CardImplementation):
    card_id = "charons_obol_lv1"

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.AFTER)
    def mark_defeated(self, ctx):
        """持有者在本次冒险中被击败：记录（结局结算时改为阵亡）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        state = ctx.game_state.scenario.vars.setdefault(_VARS_KEY, {})
        state.setdefault("defeated", []).append(ctx.investigator_id)

    def apply_scenario_xp(self, game_state, investigator_id: str, xp: int) -> int:
        """冒险结局经验结算：未被击败+2经验；被击败则标记阵亡。

        返回结算后的经验值（战役层调用；单局引擎不消费经验）。
        """
        state = game_state.scenario.vars.setdefault(_VARS_KEY, {})
        defeated = state.get("defeated", [])
        if investigator_id in defeated:
            state.setdefault("killed", []).append(investigator_id)
            game_state.log_effect("🪙 卡戎的银币：持有者在冒险中被击败，阵亡")
            return xp
        game_state.log_effect("🪙 卡戎的银币：未被击败，额外获得2点经验")
        return xp + 2
