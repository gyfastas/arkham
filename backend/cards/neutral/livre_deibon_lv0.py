"""Livre d'Eibon (Level 0) — Neutral Asset, Hand slot. Norman Withers 专属。
[fast] 横置埃本之书：将你牌库顶的牌与你手牌中的1张牌交换。
[fast] 横置埃本之书：将你牌库顶的牌投入你所在地点一位调查员进行的
一次符合条件的技能检定。

简化说明：
- 交换的手牌选择需玩家输入：activate_swap() 可传 hand_card_id，
  默认交换手牌第一张。
- "投入检定"：activate_commit() 横置并取出牌库顶牌挂起，下一次同地点
  调查员的 SKILL_TEST_COMMIT 时按该牌图标加值（matching+wild），
  检定结束后投入牌进入弃牌堆（官方投入牌结算后弃置）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class LivreDeibon(CardImplementation):
    card_id = "livre_deibon_lv0"
    activations = [
        {
            "id": "swap",
            "label": "【快速】横置：牌库顶牌与1张手牌交换",
            "method": "activate_swap",
        },
        {
            "id": "commit",
            "label": "【快速】横置：牌库顶牌投入同地点检定",
            "method": "activate_commit",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_commit: str | None = None  # 挂起的投入牌 card_id

    def activate_swap(self, game_state, investigator_id,
                      hand_card_id: str | None = None) -> bool:
        """[fast] 横置：牌库顶牌与1张手牌交换。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or inst.exhausted:
            return False
        if not inv.deck or not inv.hand:
            return False
        if hand_card_id is None:
            hand_card_id = inv.hand[0]
        if hand_card_id not in inv.hand:
            return False
        inst.exhausted = True
        top = inv.deck.pop(0)
        inv.hand.remove(hand_card_id)
        inv.hand.append(top)
        inv.deck.insert(0, hand_card_id)
        game_state.log_effect(
            f"📖 埃本之书：牌库顶牌与【{game_state.card_name(hand_card_id)}】交换"
        )
        return True

    def activate_commit(self, game_state, investigator_id) -> bool:
        """[fast] 横置：牌库顶牌投入下一次同地点检定的投入步骤。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or inst.exhausted:
            return False
        if not inv.deck or self._pending_commit is not None:
            return False
        inst.exhausted = True
        self._pending_commit = inv.deck.pop(0)
        game_state.log_effect(
            f"📖 埃本之书：【{game_state.card_name(self._pending_commit)}】"
            "将投入下一次检定"
        )
        return True

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def commit_icons(self, ctx):
        if self._pending_commit is None:
            return
        owner = ctx.game_state.get_card_instance(self.instance_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or inv is None:
            return
        owner_inv = ctx.game_state.get_investigator(owner.controller_id)
        if owner_inv is None or inv.location_id != owner_inv.location_id:
            return
        data = ctx.game_state.get_card_data(self._pending_commit)
        icons = 0
        if data is not None and data.skill_icons:
            icons += data.skill_icons.get(ctx.skill_type.value, 0)
            icons += data.skill_icons.get("wild", 0)
        if icons:
            ctx.modify_amount(icons, "livre_deibon_commit")
        ctx.committed_cards.append(self._pending_commit)
        ctx.game_state.log_effect(
            f"📖 埃本之书：投入【{ctx.game_state.card_name(self._pending_commit)}】"
            f"（+{icons}图标）"
        )

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def discard_committed(self, ctx):
        if self._pending_commit is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        owner_id = inst.controller_id if inst else ctx.investigator_id
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is not None:
            owner.discard.append(self._pending_commit)
        self._pending_commit = None
