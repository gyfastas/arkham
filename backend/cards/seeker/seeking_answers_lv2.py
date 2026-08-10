"""Seeking Answers (Level 2) — Seeker Event.
调查。如果你成功，不发现你所在地点的1条线索，改为在你所在地点与
各连接地点之间共发现2条线索。

简化说明：
- 打出后由会话层发起调查行动：本实现武装后，基础发现（本地点1条）照
  常结算，随后自动补第2条（优先第一个有线索的连接地点，否则本地点）；
- 若本地点没有线索（基础发现不发生），成功时从连接地点共取2条
  （自动从第一个有线索的连接地点取，不足则顺延到下一个）；
- 线索在地点间的分配为自动规则（官方由玩家自选），如需选择 UI 需会话层接线。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_ARM = "seeking_answers_lv2_armed"
_DONE = "seeking_answers_lv2_done"


class SeekingAnswersLv2(CardImplementation):
    card_id = "seeking_answers_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "seeking_answers_lv2":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if not hasattr(inv, "active_effects"):
            inv.active_effects = {}
        inv.active_effects[_ARM] = True
        inv.active_effects[_DONE] = False

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def bonus_second_clue(self, ctx):
        """基础发现（本地点1条）结算后：再发现第2条（优先连接地点）。"""
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", {})
        if not effects.get(_ARM) or effects.get(_DONE):
            return
        effects[_DONE] = True
        taken = self._take_from_connecting(ctx, inv, count=1)
        if not taken:
            origin = ctx.game_state.get_location(ctx.location_id or inv.location_id)
            if origin is not None and origin.clues > 0:
                origin.clues -= 1
                inv.clues += 1
                taken = True
        if taken:
            ctx.game_state.log_effect("🔎 寻找答案(2)：共发现2条线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def end_test(self, ctx):
        """本地点无线索（基础发现未发生）：成功时从连接地点共取2条。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        effects = getattr(inv, "active_effects", {}) if inv else {}
        armed = effects.pop(_ARM, False)
        done = effects.pop(_DONE, False)
        investigating = self._investigating
        self._investigating = None
        if not armed or not (ctx.success and not done):
            return
        if inv is None or investigating != ctx.investigator_id:
            return
        if self._take_from_connecting(ctx, inv, count=2):
            ctx.game_state.log_effect("🔎 寻找答案(2)：从连接地点发现2条线索")

    def _take_from_connecting(self, ctx, inv, count: int) -> bool:
        """从连接地点取至多 count 条线索；取到至少1条返回 True。"""
        origin = ctx.game_state.get_location(inv.location_id)
        if origin is None:
            return False
        taken_any = False
        for conn_id in getattr(origin, "connections", []) or []:
            if count <= 0:
                break
            conn = ctx.game_state.get_location(conn_id)
            if conn is None:
                continue
            while count > 0 and conn.clues > 0:
                conn.clues -= 1
                inv.clues += 1
                count -= 1
                taken_any = True
        return taken_any
