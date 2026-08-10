"""Ace of Rods (Level 1) — Neutral Asset, Tarot slot.
[fast] 你的回合中，将权杖王牌从游戏中移除：本回合你可以进行1个额外行动，
在该行动期间你的每项技能+2。
[reaction] 当游戏开始时，若权杖王牌在你的起始手牌中：将其放置入场。

简化说明：
- 额外行动的"+2每项技能"近似为持续到本回合结束（官方仅限额外行动期间；
  引擎不区分哪个行动是"额外"的——简化注明），INVESTIGATOR_TURN_ENDS 清除。
- "从游戏中移除"记入 scenario.vars["removed_from_game"]（同一惯例）。
- 游戏开始时的入场由会话层在起始手牌结算时调用
  put_into_play_at_game_begin()（引擎无 GAME_BEGINS 事件——缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class AceOfRods(CardImplementation):
    card_id = "ace_of_rods_lv1"
    activations = [{
        "id": "remove_for_action",
        "label": "[快速] 移出游戏：额外1行动，技能+2",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._boost_active = False  # 技能+2生效中（本回合）

    def activate(self, game_state, investigator_id) -> bool:
        """[fast] 你的回合中：移出游戏，+1行动，本回合技能+2。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        game_state.scenario.vars.setdefault(
            "removed_from_game", []).append("ace_of_rods_lv1")
        inv.actions_remaining += 1
        self._boost_active = True
        game_state.log_effect("🪄 权杖王牌：移出游戏，额外1行动且技能+2")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_boost(self, ctx):
        """额外行动期间每项技能+2（简化：持续到回合结束）。"""
        if not self._boost_active:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "ace_of_rods_boost")

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_boost(self, ctx):
        self._boost_active = False

    def put_into_play_at_game_begin(self, game_state, investigator_id) -> bool:
        """[reaction] 游戏开始时在起始手牌中：放置入场（会话层调用，免费用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "ace_of_rods_lv1" not in inv.hand:
            return False
        inv.hand.remove("ace_of_rods_lv1")
        from backend.models.state import CardInstance
        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="ace_of_rods_lv1",
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)
        return True
