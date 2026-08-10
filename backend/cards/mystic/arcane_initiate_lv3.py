"""Arcane Initiate (Level 3) — Mystic Asset, Ally slot. (03271)
<b>强制</b> - 在新晋术士入场后：在其上放置1个毁灭标记或2点恐惧。
[fast] 横置新晋术士：在你牌库顶3张牌中查找并抽取1张[[法术]]卡，混洗你的牌库。

简化说明：
- 入场强制的二选一无选择 UI：默认放置2点恐惧（通常比推进毁灭轨道更有利）；
  可在 CARD_PLAYED/CARD_ENTERS_PLAY 的 ctx.extra["choose_doom"]=True 改为放毁灭。
- 搜索只命中牌库顶3张中的第一张法术卡（同 lv0）；未命中则仅洗牌。
"""

from backend.cards.base import on_event
from backend.cards.mystic.arcane_initiate_lv0 import ArcaneInitiate
from backend.models.enums import GameEvent, TimingPriority


class ArcaneInitiateLv3(ArcaneInitiate):
    card_id = "arcane_initiate_lv3"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """强制 - 入场后：放置1毁灭或2恐惧（默认2恐惧）。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if ctx.extra.get("choose_doom"):
            inst.doom += 1
            ctx.extra["arcane_initiate_doom"] = True
        else:
            inst.horror += 2
            ctx.extra["arcane_initiate_horror"] = 2
