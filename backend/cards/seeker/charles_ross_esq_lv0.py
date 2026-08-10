"""Charles Ross, Esq. (Level 0) — Seeker Asset, Ally slot.
你可以花费资源来支付你所在地点其他调查员打出的[[Item]]支援。
[快速]横置查尔斯·罗斯大人：你所在地点的调查员打出的下一张
[[Item]]支援费用降低1点。

简化说明：
- 费用降低实现为"入场后返还1资源"：引擎的出牌支付流程（actions._play）
  没有费用修正钩子，无法在支付前减免；因此资源不足原价但足以支付折后价的
  出牌仍会失败（引擎缺口，见实现报告）；
- "代其他调查员支付道具费用"需要引擎支付流程支持第三方支付，
  同为引擎缺口，本卡内不实现。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class CharlesRossEsq(CardImplementation):
    card_id = "charles_ross_esq_lv0"
    activations = [{
        "id": "discount",
        "label": "【快速】横置：本地点下一张道具支援费用-1",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """【快速】横置：本地点下一张道具支援费用-1（返还实现）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        game_state.log_effect("🎩 查尔斯·罗斯大人：本地点下一张道具支援费用-1")
        return True

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def refund_item_discount(self, ctx):
        """本地点调查员的道具支援入场时：返还1资源（折后价实现）。"""
        if not self._armed:
            return
        ross = ctx.game_state.get_card_instance(self.instance_id)
        if ross is None:
            return
        owner = ctx.game_state.get_investigator(ross.controller_id)
        played_inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or played_inv is None:
            return
        if played_inv.location_id != owner.location_id:
            return
        cd = ctx.game_state.get_card_data(ctx.extra.get("card_id") or "")
        if cd is None or "item" not in [t.lower() for t in (cd.traits or [])]:
            return
        self._armed = False
        played_inv.resources += 1
        ctx.extra["charles_ross_discount"] = True
        ctx.game_state.log_effect(
            f"🎩 查尔斯·罗斯大人：【{ctx.game_state.card_name(cd.id)}】费用-1"
        )
