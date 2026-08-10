"""Leadership (Level 2) — Guardian Skill. (06235)
当领导力被投入到另一位调查员进行的技能检定时，领导力获得
[意志][wild]图标。
如果本次检定成功，获得2资源。如果领导力被投入到另一位调查员进行的
技能检定，该调查员也获得2资源。

简化说明：
- 图标加值在 SKILL_TEST_COMMIT 结算：投入卡列表含本卡且持有者在场
  （手牌中）且不是检定执行者时，额外+2图标（引擎按卡面只计1个wild）。
- 投入他人检定的归属判定：检定执行者之外、手牌含本卡的调查员视为持有者
  （引擎不跟踪他人投入的来源，引擎缺口注明）。
- 引擎 ST.8 只弃置执行者手牌中的投入卡；投入到他人检定的本卡由本实现
  在 SKILL_TEST_ENDS 时从持有者手牌弃置（补引擎缺口）。
- 成功资源：持有者+2；投入他人检定时执行者也+2。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Leadership(CardImplementation):
    card_id = "leadership_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._owner_id: str | None = None
        self._performer_id: str | None = None

    @staticmethod
    def _find_owner(game_state, performer_id: str):
        """持有者：手牌含本卡的调查员（优先非执行者——投入他人检定的情形）。"""
        fallback = None
        for inv in game_state.investigators.values():
            if "leadership_lv2" not in inv.hand:
                continue
            if inv.investigator_id != performer_id:
                return inv
            fallback = inv
        return fallback

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def commit_bonus(self, ctx):
        """投入他人检定时：本卡额外获得[意志][wild]（+2图标）。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        owner = self._find_owner(ctx.game_state, ctx.investigator_id)
        if owner is None:
            return
        self._owner_id = owner.investigator_id
        self._performer_id = ctx.investigator_id
        if owner.investigator_id != ctx.investigator_id:
            ctx.modify_amount(2, "leadership_extra_icons")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def gain_resources(self, ctx):
        """成功：持有者+2资源；投入他人检定时执行者也+2。"""
        if self.card_id not in (ctx.committed_cards or []):
            return
        owner_id = self._owner_id
        performer_id = self._performer_id or ctx.investigator_id
        if owner_id is None:
            owner = self._find_owner(ctx.game_state, performer_id)
            owner_id = owner.investigator_id if owner else None
        owner = ctx.game_state.get_investigator(owner_id) if owner_id else None
        if owner is not None:
            owner.resources += 2
        if owner_id is not None and performer_id != owner_id:
            performer = ctx.game_state.get_investigator(performer_id)
            if performer is not None:
                performer.resources += 2
        ctx.extra["leadership_resources"] = True
        ctx.game_state.log_effect("🎖️ 领导力：检定成功，获得2资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_from_owner(self, ctx):
        """投入到他人检定的本卡从持有者手牌弃置（引擎只处理执行者手牌）。"""
        owner_id, performer_id = self._owner_id, self._performer_id
        self._owner_id = self._performer_id = None
        if owner_id is None or owner_id == performer_id:
            return
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is not None and self.card_id in owner.hand:
            owner.hand.remove(self.card_id)
            owner.discard.append(self.card_id)
