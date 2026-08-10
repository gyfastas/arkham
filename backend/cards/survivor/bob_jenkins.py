"""Bob Jenkins — Survivor Investigator. (08016)
能力：在任何时候，你所在地点的调查员可以向你揭示其手中的[[Item]]支援卡。
在你回合中，你可以进行一个额外行动，该行动只能用于打出你所在地点调查员
手中的一张[[Item]]支援卡，置于该调查员控制之下（双方调查员都可以花费
资源来支付其费用）。
远古印记：你每控制1张[[Item]]支援卡，+1。

简化说明：
- "向你揭示手中的道具"为信息展示，引擎无状态，不实现（UI 交互）。
- 额外行动实现为公开方法 activate_play_item()（参考 skids_otoole 的
  activate_extra_action 模式，由 UI 调用）：通过 INVESTIGATOR_TURN_BEGINS/
  ENDS 跟踪回合，鲍勃每回合有1个"道具行动"（_item_action_available）。
  该行动不扣 actions_remaining；按官方规则打牌行动会引起趁乱攻击，但
  AoO 结算在 ActionResolver 内部，卡牌代码无法触发——引擎缺口。
- 费用分摊简化为自动：持有者先支付其全部可付部分，余下由鲍勃支付；
  合计不足则失败（官方为双方协商分摊，可由 UI 传 bob_pays 显式指定
  鲍勃出资额）。
- 打出置于持有者控制之下：实例 owner/controller 均为持有者，占用持有者
  槽位。卡牌能力注册需 CardRegistry（卡实现拿不到）——引擎缺口，
  会话层可对 ctx 日志中的实例补注册（同 ever_vigilant 惯例）。
- 远古印记：按鲍勃场上 traits 含 "item" 的支援数量 +N。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance


def _is_item_asset(game_state, card_id) -> bool:
    cd = game_state.get_card_data(card_id)
    return (cd is not None and cd.type == CardType.ASSET
            and "item" in (cd.traits or []))


class BobJenkins(CardImplementation):
    card_id = "bob_jenkins"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._item_action_available = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _get_bob(self, game_state, investigator_id):
        """Return the investigator state iff it is Bob Jenkins."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "bob_jenkins":
            return None
        return inv

    # ------------------------------------------------------------------
    # 每回合1个"打出同地点调查员手中道具"的额外行动
    # ------------------------------------------------------------------

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def on_turn_begins(self, ctx):
        if self._get_bob(ctx.game_state, ctx.investigator_id) is not None:
            self._item_action_available = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.WHEN)
    def on_turn_ends(self, ctx):
        if self._get_bob(ctx.game_state, ctx.investigator_id) is not None:
            self._item_action_available = False

    def activate_play_item(self, game_state, investigator_id, owner_id: str,
                           card_id: str, bob_pays: int | None = None) -> bool:
        """额外行动：打出同地点调查员手中的一张[[Item]]支援，置于其控制下。

        bob_pays：显式指定鲍勃出资额（None=自动：持有者先付，余下鲍勃补）。
        由 UI 在玩家选择发动时调用。
        """
        bob = self._get_bob(game_state, investigator_id)
        if bob is None or not self._item_action_available:
            return False
        owner = game_state.get_investigator(owner_id)
        if owner is None or owner.location_id != bob.location_id:
            return False
        if card_id not in owner.hand or not _is_item_asset(game_state, card_id):
            return False

        data = game_state.get_card_data(card_id)
        cost = data.cost or 0

        # 费用分摊
        if bob_pays is None:
            bob_share = max(0, cost - owner.resources)
        else:
            bob_share = max(0, min(bob_pays, cost))
        owner_share = cost - bob_share
        if bob.resources < bob_share or owner.resources < owner_share:
            return False

        # 槽位检查（占用持有者槽位）
        slot_mgr = getattr(game_state, "slot_managers", {}).get(owner_id)
        if data.slots and slot_mgr is not None and not slot_mgr.can_play_card(
                data.slots, data.traits):
            return False

        bob.resources -= bob_share
        owner.resources -= owner_share
        owner.hand.remove(card_id)
        self._item_action_available = False

        inst_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=inst_id,
            card_id=card_id,
            owner_id=owner_id,
            controller_id=owner_id,
            slot_used=list(data.slots or []),
        )
        if data.uses:
            inst.uses = dict(data.uses)
        game_state.cards_in_play[inst_id] = inst
        owner.play_area.append(inst_id)
        if slot_mgr is not None and data.slots:
            slot_mgr.occupy(inst_id, data.slots, data.traits)
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=owner_id,
                target=inst_id,
                extra={"card_id": card_id},
            ))
        game_state.log_effect(
            f"💼 鲍勃·詹金斯：打出【{game_state.card_name(card_id)}】"
            f"置于{owner_id}控制之下")
        return True

    # ------------------------------------------------------------------
    # 远古印记：每控制1张[[Item]]支援 +1
    # ------------------------------------------------------------------

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：鲍勃场上每张道具支援 +1。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_bob(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        items = 0
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is not None and _is_item_asset(ctx.game_state, inst.card_id):
                items += 1
        if items:
            ctx.modify_amount(items, "bob_jenkins_elder_sign")
