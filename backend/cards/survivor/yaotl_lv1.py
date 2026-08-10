"""Yaotl (Level 1) — Survivor Asset, Ally slot. (04035)
[fast] 消耗雅沃托：在技能检定中，你每项技能获得加成，加成的点数等于你
弃牌堆顶上的1张卡牌的对应技能图标数（[wild] 图标不计算在内）。
[fast]：丢弃你牌堆顶部的1张卡牌。（每阶段限制1次。）

简化说明：
- 两个快速能力经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由）。
- 加值能力武装后对持有者的下一次技能检定生效：按弃牌堆顶卡上与受检技能
  匹配的图标数加值（不含万能图标）。
- 磨牌能力按（轮数, 阶段）记次，同阶段内不可重复使用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Yaotl(CardImplementation):
    card_id = "yaotl_lv1"
    activations = [
        {
            "id": "boost",
            "label": "消耗：本次检定按弃牌堆顶卡图标加值",
            "method": "activate_boost",
        },
        {
            "id": "mill",
            "label": "丢弃牌堆顶1张卡（每阶段1次）",
            "method": "activate_mill",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._boost_armed = False
        self._last_mill: tuple | None = None

    def activate_boost(self, game_state, investigator_id: str) -> bool:
        """[fast] 消耗：下一次技能检定按弃牌堆顶卡图标加值。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if not inv.discard:
            return False
        inst.exhausted = True
        self._boost_armed = True
        game_state.log_effect("🐆 雅沃托：消耗，本次检定按弃牌堆顶卡图标加值")
        return True

    def activate_mill(self, game_state, investigator_id: str) -> bool:
        """[fast] 丢弃牌堆顶1张卡（每阶段1次）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        key = (game_state.scenario.round_number,
               game_state.scenario.current_phase)
        if self._last_mill == key:
            return False
        if not inv.deck:
            return False
        self._last_mill = key
        card_id = inv.deck.pop(0)
        inv.discard.append(card_id)
        game_state.log_effect(
            f"🐆 雅沃托：丢弃牌堆顶【{game_state.card_name(card_id)}】")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """按弃牌堆顶卡上与受检技能匹配的图标数加值（不含万能）。"""
        if not self._boost_armed or ctx.skill_type is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.owner_id != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not inv.discard:
            return
        top = ctx.game_state.get_card_data(inv.discard[-1])
        if top is None:
            return
        bonus = (top.skill_icons or {}).get(ctx.skill_type.value, 0)
        if bonus:
            ctx.modify_amount(bonus, "yaotl_boost")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._boost_armed = False
