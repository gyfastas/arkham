"""Seeking Answers (Level 0) — Seeker Event.
调查。如果你成功，不发现你所在地点的线索，改为发现一个连接地点的1条线索。

简化说明：
- 打出后由会话层发起调查行动（与 Burglary 同模式）：本实现武装后在
  CLUE_DISCOVERED 时把基础发现重定向到连接地点；
- 连接地点的选择简化为"第一个有线索的连接地点"；
- 若你所在地点本就没有线索（基础发现不发生），成功时仍可在连接地点发现1条；
- 若所有连接地点都没有线索，保留本地点的基础发现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_ARM = "seeking_answers_lv0_armed"
_DONE = "seeking_answers_lv0_done"


class SeekingAnswers(CardImplementation):
    card_id = "seeking_answers_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "seeking_answers_lv0":
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
    def redirect_base_clue(self, ctx):
        """基础发现发生时：改为从连接地点取（事后校正，与 Burglary 同模式）。"""
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        effects = getattr(inv, "active_effects", {})
        if not effects.get(_ARM) or effects.get(_DONE):
            return
        origin = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        conn = self._first_connecting_with_clues(ctx, origin)
        if conn is None:
            return  # 连接地点均无线索：保留基础发现
        if origin is not None:
            origin.clues += 1  # 返还本地点的基础发现
        inv.clues = max(0, inv.clues - 1)
        conn.clues -= 1
        inv.clues += 1
        effects[_DONE] = True
        ctx.extra["seeking_answers_connected"] = conn.location_id
        ctx.game_state.log_effect("🔎 寻找答案：改为在连接地点发现1条线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def end_test(self, ctx):
        """本地点无线索导致基础发现未发生时：成功仍可在连接地点发现1条。"""
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
        origin = ctx.game_state.get_location(inv.location_id)
        conn = self._first_connecting_with_clues(ctx, origin)
        if conn is not None:
            conn.clues -= 1
            inv.clues += 1
            ctx.game_state.log_effect("🔎 寻找答案：在连接地点发现1条线索")

    def _first_connecting_with_clues(self, ctx, origin):
        if origin is None:
            return None
        for conn_id in getattr(origin, "connections", []) or []:
            conn = ctx.game_state.get_location(conn_id)
            if conn is not None and conn.clues > 0:
                return conn
        return None
