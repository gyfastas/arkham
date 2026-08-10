""""Let God sort them out..." (Level 0) — Rogue Event. (06160)
仅在你击败了生命合计不少于6点的敌人的你的回合中才能打出。
将"让上帝来收拾他们…"加入胜利陈列区，并立即结束你的回合。本场剧本结算
获得经验时，你额外获得1点经验。

简化说明：
- 打出限制：引擎打出流程不支持前置条件（引擎缺口）；实现为打出时校验——
  条件不满足则效果不发动（卡仍按引擎流程入弃牌堆）。
- 击败生命合计经 ENEMY_DEFEATED 在 scenario.vars 中按调查员累计，
  仅在其回合内计数、回合开始时清零（本卡须在其手牌中，
  persistent_in_hand）。
- "立即结束你的回合"简化为 actions_remaining=0（回合结束流程由会话层推进）。
- 加入胜利陈列区：在回合结束（INVESTIGATOR_TURN_ENDS）时从弃牌堆/手牌
  移至 victory_display（引擎 _play_event 在 CARD_PLAYED 后才入弃牌堆，
  故延迟清理）；额外经验记入 scenario.vars["extra_experience"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_REQUIRED_HEALTH = 6


def _vars_key(investigator_id: str) -> str:
    return f"lgsto_defeated_health_{investigator_id}"


class LetGodSortThemOut(CardImplementation):
    card_id = "let_god_sort_them_out_lv0"
    persistent_in_hand = True  # 在手牌中持续累计本回合击败的敌人生命

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._holder_id: str | None = None  # 手牌持有者的回合跟踪
        self._pending_victory: str | None = None  # investigator_id

    def _holder(self, ctx, investigator_id):
        """本卡在该调查员手牌中才视为其持有者。"""
        inv = ctx.game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return None
        return inv

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_start(self, ctx):
        if self._holder(ctx, ctx.investigator_id) is not None:
            self._holder_id = ctx.investigator_id
            ctx.game_state.scenario.vars[_vars_key(ctx.investigator_id)] = 0

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        if self._holder_id == ctx.investigator_id:
            self._holder_id = None

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def track_defeats(self, ctx):
        """累计持有者本回合击败的敌人生命（本卡须在其手牌中）。"""
        if self._holder_id != ctx.investigator_id:
            return
        if self._holder(ctx, ctx.investigator_id) is None:
            return
        cd = ctx.game_state.get_card_data(ctx.extra.get("card_id"))
        health = (cd.enemy_health or 0) if cd else 0
        if health <= 0:
            return
        key = _vars_key(ctx.investigator_id)
        ctx.game_state.scenario.vars[key] = \
            ctx.game_state.scenario.vars.get(key, 0) + health

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != "let_god_sort_them_out_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        total = ctx.game_state.scenario.vars.get(
            _vars_key(ctx.investigator_id), 0)
        if total < _REQUIRED_HEALTH:
            # 官方：不满足条件不能打出；引擎无前置校验通道，效果不发动
            ctx.game_state.log_effect(
                "😇 让上帝来收拾他们…：本回合击败敌人生命不足6，效果不发动")
            return
        inv.actions_remaining = 0  # 立即结束你的回合（简化）
        ctx.game_state.scenario.vars["extra_experience"] = \
            ctx.game_state.scenario.vars.get("extra_experience", 0) + 1
        self._pending_victory = ctx.investigator_id
        ctx.extra["let_god_sort_them_out"] = True
        ctx.game_state.log_effect(
            "😇 让上帝来收拾他们…：加入胜利陈列区，回合结束，结算+1经验")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def move_to_victory_display(self, ctx):
        """回合结束：从弃牌堆/手牌移至胜利陈列区（清理引擎入弃牌堆的副本）。"""
        if self._pending_victory != ctx.investigator_id:
            return
        self._pending_victory = None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        for pile in (inv.discard, inv.hand):
            if self.card_id in pile:
                pile.remove(self.card_id)
                break
        if self.card_id not in ctx.game_state.scenario.victory_display:
            ctx.game_state.scenario.victory_display.append(self.card_id)
