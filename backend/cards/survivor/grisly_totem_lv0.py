"""Grisly Totem (Level 0) — Survivor Asset, Accessory slot. (02238? 核心循环)
[reaction] After you commit a card to a skill test, exhaust Grisly Totem:
That card gains another instance of one of its skill icons of your choice.

简化说明：
- 图标选择自动化：复制所投入卡中与本次检定技能匹配的图标（无匹配则复制
  万能图标）；净效果恒为本次检定 +1 图标（官方为玩家任选一个该卡已有的
  图标）。
- lv3 子类追加"检定失败则该卡返回手牌"。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class GrislyTotem(CardImplementation):
    card_id = "grisly_totem_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._boosted_card: str | None = None  # 本次检定被加成的投入卡

    def _owner_in_play(self, ctx):
        """图腾在打出者装备区时返回该调查员，否则 None。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        return inv

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.AFTER)
    def duplicate_icon(self, ctx):
        """你投入一张卡后：横置图腾，该卡再获得一个其已有图标（+1）。"""
        if not ctx.committed_cards:
            return
        inv = self._owner_in_play(ctx)
        if inv is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return

        # 自动选第一张至少有一个匹配/万能图标的投入卡
        chosen = None
        for cid in ctx.committed_cards:
            cd = ctx.game_state.get_card_data(cid)
            icons = (cd.skill_icons or {}) if cd else {}
            if icons.get(ctx.skill_type.value, 0) or icons.get("wild", 0):
                chosen = cid
                break
        if chosen is None:
            return

        inst.exhausted = True
        self._boosted_card = chosen
        ctx.modify_amount(1, "grisly_totem_icon")
        ctx.game_state.log_effect(
            f"🗿 阴森图腾：横置，【{ctx.game_state.card_name(chosen)}】"
            "再获得一个其已有图标")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._boosted_card = None
