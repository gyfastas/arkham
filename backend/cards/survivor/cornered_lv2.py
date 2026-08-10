"""Cornered (Level 2) — Survivor Asset.
[快速] 丢弃你1张手牌：本次技能检定+2技能值。（每次检定限1次。）

简化说明：
- 经公开方法 spend() 由会话层在快速窗口调用：丢弃1张手牌（可经
  card_id 指定，默认第一张非本卡手牌），武装+2技能值在下一次
  SKILL_VALUE_DETERMINED 生效（不限技能，与官方"skill value"一致）。
- 每次检定限1次由 _used_this_test 控制，SKILL_TEST_ENDS 清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Cornered(CardImplementation):
    card_id = "cornered_lv2"
    activations = [{
        "id": "spend",
        "label": "快速：丢弃1张手牌，本次检定+2技能值",
        "method": "spend",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0
        self._used_this_test = False

    def spend(self, game_state, investigator_id: str,
              card_id: str | None = None) -> bool:
        """快速：丢弃1张手牌，本次检定+2技能值（每次检定限1次）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if self._used_this_test:
            return False
        if card_id is not None:
            if card_id not in inv.hand:
                return False
            discard_id = card_id
        else:
            candidates = [c for c in inv.hand if c != self.card_id]
            if not candidates:
                return False
            discard_id = candidates[0]
        inv.hand.remove(discard_id)
        inv.discard.append(discard_id)
        self._armed += 2
        self._used_this_test = True
        game_state.log_effect(
            f"🗑️ 困兽之斗：丢弃【{game_state.card_name(discard_id)}】，本次检定+2技能值")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(self._armed, "cornered_boost")
        self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0
        self._used_this_test = False
