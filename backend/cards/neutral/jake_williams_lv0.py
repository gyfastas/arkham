"""Jake Williams (Level 0) — Neutral Asset, Ally slot. Ursula Downs 专属。
你每回合执行的第一个移动或调查行动不引发借机攻击。
[reaction] 在你揭示一个地点或将一个新地点放入战场后，横置杰克·威廉姆斯：
抽1张牌。

简化说明：
- "不引发借机攻击"：移动/调查发起时若为本回合首次则举盾，随后的
  ATTACK_OF_OPPORTUNITY 全部取消，行动完成时收盾。
- "揭示地点/新地点进场"无引擎事件（引擎缺口），实现为公开方法
  on_location_revealed()，由会话层在地点揭示/进场时调用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class JakeWilliams(CardImplementation):
    card_id = "jake_williams_lv0"
    activations = [{
        "id": "location_revealed",
        "label": "【响应】地点揭示/进场后横置：抽1张牌",
        "method": "on_location_revealed",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._first_used = False   # 本回合首个移动/调查已用
        self._aoo_shield = False   # 当前行动处于免借机攻击窗口

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def reset_turn(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            self._first_used = False

    @on_event(GameEvent.MOVE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def shield_move(self, ctx):
        self._maybe_shield(ctx)

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def shield_investigate(self, ctx):
        self._maybe_shield(ctx)

    def _maybe_shield(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if self._first_used:
            return
        self._first_used = True
        self._aoo_shield = True
        ctx.game_state.log_effect("🧭 杰克·威廉姆斯：本行动不引发借机攻击")

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_shield:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def drop_shield(self, ctx):
        self._aoo_shield = False

    def on_location_revealed(self, game_state, investigator_id) -> bool:
        """[reaction] 地点揭示/新地点进场后：横置，抽1张牌。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        inst.exhausted = True
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        game_state.log_effect("🧭 杰克·威廉姆斯：抽1张牌")
        return True
