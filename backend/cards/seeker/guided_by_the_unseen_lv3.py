"""Guided by the Unseen (Level 3) — Seeker Asset. (07223)
使用(4秘密)。
[快速]在你所在地点的技能检定中：执行检定的调查员可以在其牌堆顶部3张
卡牌中查找一张能投入到这次检定的卡牌。你可以花费1秘密来投入该卡牌。
混洗执行检定的调查员的牌堆。(每次检定限制1次。)

简化说明：
- 触发自动（官方两个"可以"均为玩家选择）：只要持有者与你同地点、
  本卡尚有秘密、且你牌堆顶3张内有可投入的卡牌（含本次检定技能图标或
  万能图标），即自动花费1秘密投入第一张匹配卡；
- 投入的图标经 SKILL_TEST_COMMIT 的 ctx.amount 汇入（引擎 ST.2 读取）；
  投入的卡在检定结束时进入其持有者的弃牌堆（与手牌投入一致）；
- 查找后混洗牌堆（random.shuffle）；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_count, uses_spend
from backend.models.enums import GameEvent, TimingPriority


class GuidedByTheUnseen(CardImplementation):
    card_id = "guided_by_the_unseen_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_test = False
        self._committed_from_deck: tuple[str, str] | None = None  # (inv_id, card_id)

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def commit_from_deck(self, ctx):
        if self._used_this_test:
            return
        performer = ctx.game_state.get_investigator(ctx.investigator_id)
        if performer is None or not performer.deck:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        # 你所在地点的技能检定：持有者与执行者同地点
        if owner.location_id != performer.location_id:
            return
        if uses_count(inst, "secrets") < 1:
            return

        # 牌堆顶3张中第一张可投入的卡（匹配本次技能图标或万能）
        skill_key = ctx.skill_type.value if ctx.skill_type is not None else ""
        top = list(performer.deck[:3])
        chosen = None
        for cid in top:
            cd = ctx.game_state.get_card_data(cid)
            icons = (cd.skill_icons or {}) if cd else {}
            if icons.get(skill_key, 0) >= 1 or icons.get("wild", 0) >= 1:
                chosen = cid
                break
        if chosen is None:
            return

        uses_spend(inst, "secrets")
        self._used_this_test = True

        cd = ctx.game_state.get_card_data(chosen)
        icons = (cd.skill_icons or {}) if cd else {}
        value = icons.get(skill_key, 0) + icons.get("wild", 0)

        performer.deck.remove(chosen)
        random.shuffle(performer.deck)
        ctx.modify_amount(value, "guided_by_the_unseen_commit")
        self._committed_from_deck = (performer.investigator_id, chosen)
        ctx.extra["guided_by_the_unseen_committed"] = chosen
        ctx.game_state.log_effect(
            f"🌌 冥冥指引：花费1秘密，从牌堆顶投入"
            f"【{ctx.game_state.card_name(chosen)}】（+{value}图标）"
        )

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_committed_and_clear(self, ctx):
        """投入的卡（来自牌堆）在检定结束后进入弃牌堆；清除每检定限制。"""
        self._used_this_test = False
        if self._committed_from_deck is None:
            return
        inv_id, card_id = self._committed_from_deck
        self._committed_from_deck = None
        inv = ctx.game_state.get_investigator(inv_id)
        if inv is not None and card_id not in inv.discard:
            inv.discard.append(card_id)
