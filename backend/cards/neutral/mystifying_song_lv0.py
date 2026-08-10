"""Mystifying Song (Level 0) — Neutral Event. Marie Lambeau 专属。
快速。当议程即将因达到毁灭阈值而推进时打出。
直到本阶段结束，议程不能因达到毁灭阈值而推进。
将迷惑之歌移出游戏。

简化说明：
- 引擎 MythosPhase._check_doom_threshold 不响应事件取消（引擎缺口），
  本卡在 AGENDA_ADVANCED 后回退议程序号，并把议程上的毁灭恢复到阈值
  检查时记录的总值（地点/卡牌上的毁灭已被引擎清零，此为已知偏差）。
- "移出游戏"记录于 scenario.vars["removed_from_game"]（引擎 _play_event
  会无条件置入弃牌堆，会话层应以 vars 为准）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class MystifyingSong(CardImplementation):
    card_id = "mystifying_song_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._doom_total = 0

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def arm(self, ctx):
        if ctx.extra.get("card_id") != "mystifying_song_lv0":
            return
        self._armed = True
        ctx.game_state.scenario.vars.setdefault(
            "removed_from_game", []
        ).append("mystifying_song_lv0")
        ctx.game_state.log_effect(
            "🎵 迷惑之歌：本阶段议程不能因毁灭阈值推进；移出游戏"
        )

    @on_event(GameEvent.DOOM_THRESHOLD_CHECK, priority=TimingPriority.WHEN)
    def record_doom(self, ctx):
        if self._armed:
            self._doom_total = ctx.amount or 0

    @on_event(GameEvent.AGENDA_ADVANCED, priority=TimingPriority.AFTER)
    def revert_advance(self, ctx):
        if not self._armed:
            return
        scenario = ctx.game_state.scenario
        if scenario.current_agenda_index > 0:
            scenario.current_agenda_index -= 1
        scenario.doom_on_agenda = self._doom_total
        ctx.game_state.log_effect("🎵 迷惑之歌：议程推进被阻止")

    @on_event(GameEvent.MYTHOS_PHASE_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._doom_total = 0
