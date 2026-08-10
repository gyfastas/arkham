"""Accursed Follower (Level 0) — Neutral Enemy, Basic Weakness.
生成 - 离你最远的地点。冷漠。
强制 - 敌军阶段结束时：向混沌袋中加入1个[curse]标记。

简化说明：
- 敌人弱点经 emit_card_drawn 注册后由会话层生成入场；本实现只负责
  在场期间的强制效果（实例在 cards_in_play 中即视为在场）。
- 生成位置（最远地点）与"冷漠"关键词由引擎/会话层处理（同
  the_thing_that_follows_lv0 的说明）。
- 混沌袋通过 bind_chaos_bag() 注入；未绑定时强制效果不触发。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class AccursedFollower(CardImplementation):
    card_id = "accursed_follower_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.ENEMY_PHASE_ENDS, priority=TimingPriority.FORCED)
    def add_curse_at_enemy_phase_end(self, ctx):
        """敌军阶段结束时：向混沌袋中加入1个[curse]标记。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.card_id != "accursed_follower_lv0":
            return
        if self._chaos_bag is None:
            return
        self._chaos_bag.add_token(ChaosTokenType.CURSE)
        ctx.extra["accursed_follower_curse"] = True
        ctx.game_state.log_effect("🐍 诅咒追随者：混沌袋加入1个[curse]标记")
