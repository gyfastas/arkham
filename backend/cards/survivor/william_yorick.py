"""William Yorick — Survivor Investigator.
能力：[reaction]在你击败敌人后：从你的弃牌堆(支付其费用)打出一张支援卡。
(每轮限制1次。)
远古印记：+2。如果本次检定成功，将你弃牌堆中的1张卡牌返回你的手牌。

简化说明：
- "你击败"的归属判断：优先用 ENEMY_DEFEATED ctx.investigator_id（引擎
  DamageEngine 会传 defeated_by）；缺失时回退 DAMAGE_DEALT 的最后伤害来源
  记录与威胁区归属（与 roland_banks 同一套兜底）。
- 从弃牌堆打出的支援：自动选择弃牌堆顶（最后进入）第一张费用可负担的支援卡
  （官方为玩家选择）；可在触发前设置
  scenario.vars["yorick_asset_choice_{investigator_id}"] = card_id 指定
  （须在弃牌堆中且可负担）。无可打出目标时不触发、不消耗限次（视为放弃）。
- 打出走 sleight_of_hand 同一入场通道：初始化 uses、登记槽位、发出
  CARD_ENTERS_PLAY；被打出支援的 CardImplementation 注册需要 registry 引用
  （卡实现拿不到）——引擎缺口：其 on_event 能力不生效（同 sleight_of_hand）。
- 远古印记的"将你弃牌堆中的1张卡牌返回手牌"：自动选弃牌堆顶（官方为玩家
  选择）；可在检定前设置 scenario.vars["william_yorick_return"] = card_id
  指定（须在弃牌堆中）。官方结算时点在检定成功后、投入卡进弃牌堆之前
  （引擎 ST.8 才弃投入卡），因此本检定投入的卡不会被选回，与官方一致。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)
from backend.models.state import CardInstance


def _choice_key(investigator_id: str) -> str:
    return f"yorick_asset_choice_{investigator_id}"


class WilliamYorick(CardImplementation):
    card_id = "william_yorick"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_round = False
        self._elder_sign_armed = False
        self._last_damager: dict[str, str] = {}  # enemy instance_id -> investigator_id
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 打出支援需要经事件总线发出 CARD_ENTERS_PLAY

    def _get_yorick(self, game_state, investigator_id):
        """Return the investigator state iff it is William Yorick."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "william_yorick":
            return None
        return inv

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        """每轮开始时重置限次。"""
        self._used_this_round = False

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.AFTER)
    def track_damager(self, ctx):
        """记录每个敌人最后受到的伤害来源，用于 ENEMY_DEFEATED 归属兜底。"""
        if ctx.target and ctx.investigator_id:
            self._last_damager[ctx.target] = ctx.investigator_id

    def _find_defeater(self, ctx) -> str | None:
        """判断击败者：事件自带 defeated_by 优先，回退伤害记录与威胁区。"""
        if ctx.investigator_id is not None:
            return ctx.investigator_id
        defeater = self._last_damager.get(ctx.target)
        if defeater is not None:
            return defeater
        for inv_id, inv in ctx.game_state.investigators.items():
            if ctx.target in inv.threat_area:
                return inv_id
        return None

    def _select_asset(self, ctx, inv) -> str | None:
        """选择弃牌堆中可负担的支援卡：预设优先，否则弃牌堆顶第一张。"""
        scenario = getattr(ctx.game_state, "scenario", None)
        override = None
        if scenario is not None:
            override = scenario.vars.pop(_choice_key(inv.investigator_id), None)

        def playable(card_id) -> bool:
            if card_id not in inv.discard:
                return False
            cd = ctx.game_state.get_card_data(card_id)
            return (
                cd is not None
                and cd.type == CardType.ASSET
                and inv.resources >= (cd.cost or 0)
            )

        if override is not None:
            return override if playable(override) else None
        for card_id in reversed(inv.discard):
            if playable(card_id):
                return card_id
        return None

    def _play_asset_from_discard(self, ctx, inv, card_id) -> str | None:
        """支付费用并从弃牌堆打出支援（镜像 engine.actions._play_asset）。"""
        card_data = ctx.game_state.get_card_data(card_id)
        inv.resources -= card_data.cost or 0
        inv.discard.remove(card_id)

        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(card_data.slots or []),
        )
        if card_data.uses:
            inst.uses = dict(card_data.uses)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(inv.investigator_id)
        if slot_mgr is not None and card_data.slots:
            slot_mgr.occupy(instance_id, card_data.slots, card_data.traits)

        ctx.game_state.log_effect(
            f"⚰️ 威廉·约里克：击败敌人，从弃牌堆打出"
            f"【{ctx.game_state.card_name(card_id)}】"
        )
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=inv.investigator_id,
                target=instance_id,
                extra={"card_id": card_id},
            ))
        return instance_id

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def play_asset_on_defeat(self, ctx):
        """在你击败敌人后：从弃牌堆(支付费用)打出一张支援卡（每轮限1次）。"""
        if self._used_this_round or not ctx.target:
            return
        self._last_damager.pop(ctx.target, None)
        inv = self._get_yorick(ctx.game_state, self._find_defeater(ctx))
        if inv is None:
            return

        card_id = self._select_asset(ctx, inv)
        if card_id is None:
            return  # 无可打出目标：视为放弃，不消耗限次

        self._used_this_round = True
        ctx.extra["william_yorick_played"] = self._play_asset_from_discard(
            ctx, inv, card_id
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2。武装"检定成功后弃牌堆1张卡回手"。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_yorick(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "william_yorick_elder_sign")
        self._elder_sign_armed = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def return_card_on_success(self, ctx):
        """本次检定成功：将弃牌堆1张卡返回手牌（简化：自动选弃牌堆顶）。"""
        if not self._elder_sign_armed:
            return
        self._elder_sign_armed = False
        inv = self._get_yorick(ctx.game_state, ctx.investigator_id)
        if inv is None or not inv.discard:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        override = None
        if scenario is not None:
            override = scenario.vars.pop("william_yorick_return", None)
        chosen = (
            override if override in inv.discard
            else inv.discard[-1]
        )
        inv.discard.remove(chosen)
        inv.hand.append(chosen)
        ctx.extra["william_yorick_returned"] = chosen
        ctx.game_state.log_effect(
            f"⚰️ 威廉·约里克：远古印记，"
            f"【{ctx.game_state.card_name(chosen)}】从弃牌堆返回手牌"
        )

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._elder_sign_armed = False
