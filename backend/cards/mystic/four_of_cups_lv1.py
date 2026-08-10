"""Four of Cups (Level 1) — Mystic Asset, Tarot slot. (05195)
你+1[willpower]。
[reaction] 游戏开始时，如果四圣杯在你的起始手牌中：将它放置入场。

简化说明：
- 起始入场挂 CARD_DRAWN：设置阶段（Phase.SETUP）抽到本卡时免费放置入场
  （不占行动、不付费用），并占用塔罗槽。draw_hooks 因本卡进入 play_area
  而保留注册（persistent 判定按 card_id 扫描 play_area），本实现的事件处理
  也按 card_id 识别入场实例，故注册在临时 instance_id 下仍能正常工作。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Phase, Skill, SlotType, TimingPriority
from backend.models.state import CardInstance


class FourOfCups(CardImplementation):
    card_id = "four_of_cups_lv1"

    def _in_play(self, game_state, inv) -> bool:
        return any(
            (ci := game_state.get_card_instance(iid)) is not None
            and ci.card_id == self.card_id
            for iid in inv.play_area
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """+1意志（入场后）。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self._in_play(ctx.game_state, inv):
            ctx.modify_amount(1, f"{self.card_id}_bonus")

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def put_into_play_at_setup(self, ctx):
        """游戏开始时在起始手牌中：放置入场（免费）。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        if ctx.game_state.scenario.current_phase != Phase.SETUP:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return

        inv.hand.remove(self.card_id)
        inst = CardInstance(
            instance_id=ctx.game_state.next_instance_id(),
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=[SlotType.TAROT],
        )
        ctx.game_state.cards_in_play[inst.instance_id] = inst
        inv.play_area.append(inst.instance_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr is not None:
            slot_mgr.occupy(inst.instance_id, [SlotType.TAROT],
                            ["tarot"])
        ctx.extra["four_of_cups_entered_play"] = True
