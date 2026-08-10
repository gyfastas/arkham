"""Norman Withers — Seeker Investigator. (08004)
能力：你牌堆顶部的卡牌始终揭示。
每轮1次，你可以-1资源费用打出你牌堆顶部的卡牌，如同其为你的手牌。
强制 - 在你的牌堆顶部揭示弱点后：将其抽取。
远古印记：+X。你可以用你1张手牌交换你牌堆顶部的卡牌。X为你牌堆顶部卡牌的资源费用。

简化说明：
- "牌堆顶始终揭示"为信息展示，引擎无状态；公开方法 top_card() 供 UI 查询。
- 打出牌堆顶：公开方法 activate_play_top_card()（参考 sefina_rousseau 的
  activate_draw_beneath 模式，由 UI 调用）。消耗1个行动（fast 卡除外），
  费用-1（最低0），支援走槽位检查；事件仅发出 CARD_PLAYED 后入弃牌堆——
  事件牌面效果的临时激活需 CardRegistry，卡牌代码拿不到（引擎缺口，
  同 ever_vigilant 惯例）。打行动牌不引起趁乱攻击（AoO 结算在
  ActionResolver 内部，卡牌代码无法触发——引擎缺口）。
- 强制抽弱点：挂 CARD_DRAWN（任何抽牌后检查新牌堆顶）、ROUND_BEGINS，
  以及打出牌堆顶/远古印记交换之后；抽到非弱点为止（弱点连抽会连锁）。
  抽取直接移动牌库顶到手牌并发出裸 CARD_DRAWN（未经 draw_hooks 临时激活
  弱点实现——引擎缺口，弱点的显现能力需会话层补注册）。
- 远古印记的"你可以交换"：检定同步流程中无法等待选择，实现为
  scenario.vars["norman_elder_sign_swap"] 预设（公开方法
  choose_elder_sign_swap() 设置，须为手牌）。X 取交换前牌堆顶卡牌的
  资源费用（无费用/空牌堆按0）。交换后同样触发强制抽弱点检查。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)
from backend.models.state import CardInstance, is_weakness_card

PRESET_KEY = "norman_elder_sign_swap"


class NormanWithers(CardImplementation):
    card_id = "norman_withers"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._used_this_round = False
        self._drawing_weakness = False  # 防止自发的 CARD_DRAWN 递归

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _get_norman(self, game_state, investigator_id):
        """Return the investigator state iff it is Norman Withers."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "norman_withers":
            return None
        return inv

    def top_card(self, game_state, investigator_id) -> str | None:
        """牌堆顶卡牌 id（"始终揭示"的展示查询）。由 UI 调用。"""
        inv = self._get_norman(game_state, investigator_id)
        if inv is None or not inv.deck:
            return None
        return inv.deck[0]

    # ------------------------------------------------------------------
    # 每轮1次：-1费打出牌堆顶卡牌
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        self._used_this_round = False

    def activate_play_top_card(self, game_state, investigator_id) -> bool:
        """每轮1次：以-1资源费用打出牌堆顶卡牌（如同手牌）。由 UI 调用。"""
        inv = self._get_norman(game_state, investigator_id)
        if inv is None or self._used_this_round or not inv.deck:
            return False

        card_id = inv.deck[0]
        data = game_state.get_card_data(card_id)
        if data is None or data.type not in (CardType.ASSET, CardType.EVENT):
            return False
        if is_weakness_card(data):
            return False  # 弱点不能主动打出（强制能力会先将其抽走）

        fast = bool(getattr(data, "fast", False))
        if not fast and inv.actions_remaining < 1:
            return False

        cost = max(0, (data.cost or 0) - 1)
        if inv.resources < cost:
            return False

        if data.type == CardType.ASSET and data.slots:
            slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
            if slot_mgr is not None and not slot_mgr.can_play_card(
                    data.slots, data.traits):
                return False

        # 支付并移出牌堆
        if not fast:
            inv.actions_remaining -= 1
        inv.resources -= cost
        inv.deck.pop(0)
        self._used_this_round = True

        if data.type == CardType.ASSET:
            inst_id = game_state.next_instance_id()
            inst = CardInstance(
                instance_id=inst_id,
                card_id=card_id,
                owner_id=investigator_id,
                controller_id=investigator_id,
                slot_used=list(data.slots or []),
            )
            if data.uses:
                inst.uses = dict(data.uses)
            game_state.cards_in_play[inst_id] = inst
            inv.play_area.append(inst_id)
            slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
            if slot_mgr is not None and data.slots:
                slot_mgr.occupy(inst_id, data.slots, data.traits)
            if self._bus is not None:
                self._bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CARD_ENTERS_PLAY,
                    investigator_id=investigator_id,
                    target=inst_id,
                    extra={"card_id": card_id},
                ))
        else:  # EVENT：发出 CARD_PLAYED 后入弃牌堆（牌面效果注册为引擎缺口）
            if self._bus is not None:
                self._bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.CARD_PLAYED,
                    investigator_id=investigator_id,
                    extra={"card_id": card_id},
                ))
            inv.discard.append(card_id)

        game_state.log_effect(
            f"🔭 诺曼·威瑟斯：减1费打出牌堆顶的【{game_state.card_name(card_id)}】")

        # 新牌堆顶若是弱点：强制抽取
        self._draw_top_weaknesses(game_state, inv)
        return True

    # ------------------------------------------------------------------
    # 强制 - 牌堆顶揭示弱点后：将其抽取
    # ------------------------------------------------------------------

    def _draw_top_weaknesses(self, game_state, inv) -> None:
        """把牌堆顶连续的弱点全部抽入手牌（强制能力，可连锁）。"""
        if self._drawing_weakness:
            return
        self._drawing_weakness = True
        try:
            while inv.deck:
                top = inv.deck[0]
                if not is_weakness_card(game_state.get_card_data(top)):
                    break
                inv.deck.pop(0)
                inv.hand.append(top)
                game_state.log_effect(
                    f"🔭 诺曼·威瑟斯：牌堆顶揭示弱点"
                    f"【{game_state.card_name(top)}】，强制抽取")
                if self._bus is not None:
                    self._bus.emit(EventContext(
                        game_state=game_state,
                        event=GameEvent.CARD_DRAWN,
                        investigator_id=inv.investigator_id,
                        extra={"card_id": top},
                    ))
        finally:
            self._drawing_weakness = False

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def forced_weakness_draw_on_draw(self, ctx):
        """诺曼抽牌后：检查新牌堆顶是否为弱点。"""
        inv = self._get_norman(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        self._draw_top_weaknesses(ctx.game_state, inv)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def forced_weakness_draw_on_round(self, ctx):
        """每轮开始时检查牌堆顶弱点（覆盖非抽牌途径翻上的弱点）。"""
        for inv_id, inv in ctx.game_state.investigators.items():
            if self._get_norman(ctx.game_state, inv_id) is not None:
                self._draw_top_weaknesses(ctx.game_state, inv)

    # ------------------------------------------------------------------
    # 远古印记：+X（X=牌堆顶卡牌费用）；可用1张手牌交换牌堆顶卡牌
    # ------------------------------------------------------------------

    def choose_elder_sign_swap(self, game_state, investigator_id,
                               card_id: str | None) -> bool:
        """预设远古印记要换上牌堆顶的手牌（None 清除）。由 UI 调用。"""
        inv = self._get_norman(game_state, investigator_id)
        if inv is None:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        if card_id is None:
            scenario.vars.pop(PRESET_KEY, None)
            return True
        if card_id not in inv.hand:
            return False
        scenario.vars[PRESET_KEY] = card_id
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+X；若预设手牌仍在手则与牌堆顶交换，之后检查弱点强制抽取。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_norman(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        top_data = (ctx.game_state.get_card_data(inv.deck[0])
                    if inv.deck else None)
        bonus = (top_data.cost or 0) if top_data is not None else 0
        if bonus:
            ctx.modify_amount(bonus, "norman_withers_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        card_id = scenario.vars.get(PRESET_KEY) if scenario else None
        if not card_id or card_id not in inv.hand or not inv.deck:
            return
        scenario.vars.pop(PRESET_KEY, None)
        old_top = inv.deck[0]
        inv.deck[0] = card_id
        inv.hand.remove(card_id)
        inv.hand.append(old_top)
        ctx.game_state.log_effect(
            f"🔭 诺曼·威瑟斯：远古印记，【{ctx.game_state.card_name(card_id)}】"
            f"换上牌堆顶，【{ctx.game_state.card_name(old_top)}】回到手牌")
        self._draw_top_weaknesses(ctx.game_state, inv)
