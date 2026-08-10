"""Leo Anderson — Guardian Investigator.
能力：[reaction]在你回合开始后：打出一张[[盟友]]支援卡，其费用减1。
远古印记：+2。在你牌堆顶部3张卡牌中查找并抽取1张[[盟友]]支援卡。混洗你的牌堆。

简化说明：
- 回合开始后的响应式打出：同步事件流无法等待玩家选牌，实现为
  INVESTIGATOR_TURN_BEGINS 置位 + 公开方法 activate_play_ally()（由 UI/会话层
  在玩家选择后调用；card_id 缺省取手牌中第一张盟友）。窗口在打出或回合结束
  时关闭。该响应式打出不是"行动"，不扣行动、不引发趁乱攻击。
- 费用减1后的打出复刻 ActionResolver._play_asset 流程（槽位占用、注册卡面
  实现、CARD_ENTERS_PLAY），但不经过 perform_action。
- 远古印记"查找顶部3张"：简化为自动抽取其中第一张盟友（官方为玩家选择）；
  无论是否找到都混洗牌堆。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)
from backend.models.state import CardInstance


class LeoAnderson(CardImplementation):
    card_id = "leo_anderson"

    activations = [{
        "id": "play_ally",
        "label": "【响应】回合开始后：打出一张盟友支援卡，费用-1",
        "method": "activate_play_ally",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._play_pending = False

    def _get_leo(self, game_state, investigator_id):
        """Return the investigator state iff it is Leo Anderson."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "leo_anderson":
            return None
        return inv

    def _is_ally(self, game_state, card_id) -> bool:
        cd = game_state.get_card_data(card_id)
        return (
            cd is not None
            and cd.type == CardType.ASSET
            and "ally" in (cd.traits or [])
        )

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def arm_play_window(self, ctx):
        """你的回合开始后：打开费用-1打出盟友的窗口。"""
        if self._get_leo(ctx.game_state, ctx.investigator_id) is None:
            return
        self._play_pending = True
        ctx.extra["leo_anderson_play_pending"] = True

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def close_play_window(self, ctx):
        """回合结束时关闭窗口。"""
        if self._get_leo(ctx.game_state, ctx.investigator_id) is None:
            return
        self._play_pending = False

    def activate_play_ally(self, game, investigator_id, card_id=None) -> bool:
        """[reaction] 回合开始后：打出一张盟友支援卡，费用-1。由 UI 调用。

        card_id 缺省自动取手牌中第一张盟友（官方为玩家选择）。
        """
        game_state = game.state
        inv = self._get_leo(game_state, investigator_id)
        if inv is None or not self._play_pending:
            return False
        if card_id is None:
            card_id = next(
                (c for c in inv.hand if self._is_ally(game_state, c)), None)
        if card_id is None or card_id not in inv.hand \
                or not self._is_ally(game_state, card_id):
            return False

        cd = game_state.get_card_data(card_id)
        cost = max(0, (cd.cost or 0) - 1)
        if inv.resources < cost:
            return False
        slot_mgr = game.slot_managers.get(investigator_id)
        if cd.slots and slot_mgr is not None \
                and not slot_mgr.can_play_card(cd.slots, cd.traits):
            return False

        self._play_pending = False
        inv.resources -= cost
        inv.hand.remove(card_id)

        instance_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=card_id,
            owner_id=investigator_id,
            controller_id=investigator_id,
            slot_used=list(cd.slots),
        )
        if cd.uses:
            inst.uses = dict(cd.uses)
        if cd.slots and slot_mgr is not None:
            slot_mgr.occupy(instance_id, cd.slots, cd.traits)
        game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        if game.card_registry:
            game.card_registry.activate_card(
                card_id, instance_id, game.event_bus, chaos_bag=game.chaos_bag)

        from backend.engine.event_bus import EventContext
        if cost > 0:
            game.event_bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.RESOURCES_SPENT,
                investigator_id=investigator_id,
                amount=cost,
            ))
        game.event_bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id=investigator_id,
            target=instance_id,
            extra={"card_id": card_id},
        ))
        game_state.log_effect(
            f"🧭 里奥·安德森：回合开始，费用-1打出"
            f"【{game_state.card_name(card_id)}】"
        )
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。查找牌堆顶3张中的盟友并抽取，然后混洗牌堆。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_leo(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "leo_anderson_elder_sign")

        ally = next(
            (c for c in inv.deck[:3] if self._is_ally(ctx.game_state, c)), None)
        if ally is not None:
            inv.deck.remove(ally)
            inv.hand.append(ally)
            ctx.game_state.log_effect(
                f"🧭 里奥·安德森：远古印记，抽取"
                f"【{ctx.game_state.card_name(ally)}】"
            )
        random.shuffle(inv.deck)
