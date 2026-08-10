"""Guardian of the Crystallizer (Level 0) — Neutral Enemy, Weakness.
绑定（梦境结晶器）。猎手。
猎物 - 仅限拥有梦境结晶器的调查员。
结晶器守护者进场时横置。
强制 - 若场上没有梦境结晶器：将结晶器守护者放置一旁，移出游戏。

简化说明：
- 猎物/猎手与敌人生成通道由会话层负责（同 graveyard_ghouls_lv0 说明；
  敌人数值不在玩家卡 JSON 加载通道内）。
- "放置一旁"记录到 scenario.vars["out_of_play"]；场上是否有
  "crystallizer_of_dreams" 通过扫描所有调查员 play_area 判定。
  强制检查挂在 CARD_ENTERS_PLAY / CARD_LEAVES_PLAY 之后。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

CRYSTALLIZER_ID = "crystallizer_of_dreams"


class GuardianOfTheCrystallizer(CardImplementation):
    card_id = "guardian_of_the_crystallizer_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enters_play_exhausted(self, ctx):
        """进场时横置。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inst = ctx.game_state.get_card_instance(ctx.target)
        if inst is not None and inst.card_id == self.card_id:
            inst.exhausted = True
        self._check_crystallizer(ctx.game_state)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def crystallizer_left(self, ctx):
        """结晶器离场后复查。"""
        self._check_crystallizer(ctx.game_state)

    def _check_crystallizer(self, game_state) -> None:
        """强制：场上无梦境结晶器时，将本敌人放置一旁（移出游戏）。"""
        if self._crystallizer_in_play(game_state):
            return
        inst = self._find_guardian(game_state)
        if inst is None:
            return
        iid = inst.instance_id
        for inv in game_state.investigators.values():
            if iid in inv.threat_area:
                inv.threat_area.remove(iid)
        for loc in game_state.locations.values():
            if iid in loc.enemies:
                loc.enemies.remove(iid)
        game_state.cards_in_play.pop(iid, None)
        game_state.scenario.vars.setdefault("out_of_play", []).append(self.card_id)
        game_state.log_effect(
            "💠 结晶器守护者：场上无梦境结晶器，放置一旁（移出游戏）"
        )

    @staticmethod
    def _crystallizer_in_play(game_state) -> bool:
        for inv in game_state.investigators.values():
            for iid in inv.play_area:
                inst = game_state.get_card_instance(iid)
                if inst is not None and inst.card_id == CRYSTALLIZER_ID:
                    return True
        return False

    def _find_guardian(self, game_state):
        inst = game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.card_id == self.card_id:
            return inst
        for iid, ci in game_state.cards_in_play.items():
            if ci.card_id == self.card_id:
                return ci
        return None
