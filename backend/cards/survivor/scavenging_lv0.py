"""Scavenging (Level 0) — Survivor Asset.
[reaction] After you successfully investigate by 2 or more, exhaust Scavenging:
Choose an Item card in your discard pile and add it to your hand.

简化说明：
- "调查"通过 INVESTIGATE_ACTION_INITIATED 跟踪（SKILL_TEST_ENDS 清除），
  普通智力检定（如诡计卡）不触发。
- 弃牌堆中的道具卡自动选第一张（官方为玩家选择）；横置后可刷新再用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class Scavenging(CardImplementation):
    card_id = "scavenging_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._investigating: str | None = None

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_tracking(self, ctx):
        self._investigating = None

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def scavenge_item(self, ctx):
        """成功调查且超出难度2点或以上后：横置拾荒，取回弃牌堆中一张道具卡。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) < 2:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return

        # 从弃牌堆找第一张道具支援卡（简化：自动选第一张）
        found = None
        for cid in inv.discard:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.ASSET and "item" in (cd.traits or []):
                found = cid
                break
        if found is None:
            return

        # 横置拾荒，取回道具
        inst.exhausted = True
        inv.discard.remove(found)
        inv.hand.append(found)
        ctx.extra["scavenging_recovered"] = found
        ctx.game_state.log_effect(
            f"♻️ 拾荒：横置，从弃牌堆取回【{ctx.game_state.card_name(found)}】")
