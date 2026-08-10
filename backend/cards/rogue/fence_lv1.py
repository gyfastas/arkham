"""Fence (Level 1) — Rogue Asset. (04108)
[反应]当你在你的回合中打出一张[[非法]]卡时，消耗销赃人：该[[非法]]卡
获得快速。若其已有快速，改为将其费用降低1。

简化说明：
- 引擎打出流程（actions._play）在扣费/扣行动前无可取消事件
  （PLAY_ACTION_INITIATED 有定义但未发射），故采用事后校正：
  CARD_PLAYED（事件）/ CARD_ENTERS_PLAY（支援）时若打出者为持有者、
  处于持有者回合且卡牌带 illicit 特性，则消耗本卡——非快速卡退还1行动
  （视为快速），快速卡退还至多1资源（按其已付费用，不低于0）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Fence(CardImplementation):
    card_id = "fence_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._my_turn = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def track_turn_start(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        self._my_turn = inst is not None and inst.owner_id == ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def track_turn_end(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.owner_id == ctx.investigator_id:
            self._my_turn = False

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.AFTER)
    def on_event_played(self, ctx):
        self._maybe_trigger(ctx, played_card_id=ctx.extra.get("card_id"))

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def on_asset_played(self, ctx):
        if ctx.target == self.instance_id:
            return  # 打出销赃人自身不触发
        self._maybe_trigger(ctx, played_card_id=ctx.extra.get("card_id"))

    def _maybe_trigger(self, ctx, played_card_id) -> None:
        if not self._my_turn or not played_card_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        if ctx.investigator_id != inst.owner_id:
            return
        cd = ctx.game_state.get_card_data(played_card_id)
        if cd is None or "illicit" not in (cd.traits or []):
            return

        inst.exhausted = True
        if cd.fast:
            refund = min(1, cd.cost or 0)
            owner.resources += refund
            ctx.extra["fence_refund"] = refund
            ctx.game_state.log_effect(
                f"🤝 销赃人：【{ctx.game_state.card_name(played_card_id)}】费用-{refund}")
        else:
            owner.actions_remaining += 1
            ctx.extra["fence_fast"] = True
            ctx.game_state.log_effect(
                f"🤝 销赃人：【{ctx.game_state.card_name(played_card_id)}】视为快速（退还1行动）")
