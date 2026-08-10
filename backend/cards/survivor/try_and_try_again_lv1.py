"""Try and Try Again (Level 1) — Survivor Asset. (04159)
使用(3次数)。如果反复尝试没有次数，则将其丢弃。
[reaction] 在一次技能检定失败后，如果你拥有的1张技能卡被投入该次检定中，
消耗反复尝试并花费1次数：将该技能卡返回你手中。

简化说明：
- 反应能力自动触发（官方为玩家选择）：本卡在场、准备好且剩余次数≥1时，
  任何调查员的检定失败且投入了技能卡，自动消耗+1次数并取回第一张符合
  条件的技能卡到本卡拥有者手牌（"你拥有"的归属判定从简；多张时官方为
  玩家选择）。
- 投入的技能卡在 ST.8 才入弃牌堆，故取回在 SKILL_TEST_ENDS 执行
  （opportunist 模式）。
- 次数耗尽时丢弃本卡（defeat_asset 镜像引擎离场流程）。
- 数据中 uses 键为 "triess"（源数据笔误），按键名前缀兼容读取。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class TryAndTryAgain(CardImplementation):
    card_id = "try_and_try_again_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._return_card: str | None = None

    @staticmethod
    def _uses_key(inst) -> str | None:
        """次数键（兼容源数据笔误 "triess"）。"""
        return next((k for k in inst.uses if k.startswith("tries")), None)

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def mark_return(self, ctx):
        """检定失败且投入了你的技能卡：消耗+1次数，标记待取回。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        key = self._uses_key(inst)
        if key is None or inst.uses.get(key, 0) < 1:
            return
        # 你拥有的技能卡（投入者可以是任何人，但卡须属本卡拥有者）
        skill_card = next(
            (cid for cid in (ctx.committed_cards or [])
             if (cd := ctx.game_state.get_card_data(cid)) is not None
             and cd.type == CardType.SKILL),
            None,
        )
        if skill_card is None:
            return
        inst.exhausted = True
        inst.uses[key] -= 1
        self._return_card = skill_card

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def return_to_hand(self, ctx):
        """投入的卡已入弃牌堆：取回拥有者手牌；次数耗尽则丢弃本卡。"""
        card_id = self._return_card
        self._return_card = None
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if card_id is not None and inst is not None:
            owner = ctx.game_state.get_investigator(inst.owner_id)
            if owner is not None and card_id in owner.discard:
                owner.discard.remove(card_id)
                owner.hand.append(card_id)
                ctx.extra["try_and_try_again_returned"] = card_id
                ctx.game_state.log_effect(
                    f"🔁 反复尝试：【{ctx.game_state.card_name(card_id)}】返回手牌")

        if inst is None:
            return
        key = self._uses_key(inst)
        if key is not None and inst.uses.get(key, 0) <= 0:
            defeat_asset(ctx.game_state, getattr(self, "_bus", None), self.instance_id)
            ctx.game_state.log_effect("🔁 反复尝试：次数耗尽，被丢弃")

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # defeat_asset 需要事件总线句柄
