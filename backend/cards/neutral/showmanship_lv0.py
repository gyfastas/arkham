"""Showmanship (Level 0) — Neutral Asset. (07012)
仅限德克斯特·德雷克牌组。
[reaction]在一张支援卡进入你的控制下之后：直到回合结束，在结算该支援卡上
的触发能力时，你的每项技能获得+2。

简化说明：
- "仅限德克斯特牌组"为构筑限制，由卡组校验负责。
- "该支援卡上的触发能力"以 ctx.source == 该支援卡实例识别（引擎经
  SKILL_VALUE_DETERMINED 的 source 传递能力来源，与武器检定通道一致）。
- 自动记忆最近进场的支援卡（每回合一张，符合"反应每回合一次"的实战节奏；
  卡面无次数限制，若一回合进场多张仅最新一张生效，列为简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class Showmanship(CardImplementation):
    card_id = "showmanship_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._asset_instance_id: str | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def track_asset(self, ctx):
        if ctx.target == self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        cd = ctx.game_state.get_card_data(ctx.extra.get("card_id"))
        if cd is None or cd.type != CardType.ASSET:
            return
        self._asset_instance_id = ctx.target

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_boost(self, ctx):
        """结算被记忆支援卡的触发能力时：每项技能+2。"""
        if self._asset_instance_id is None or ctx.source != self._asset_instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(2, "showmanship_boost")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._asset_instance_id = None
