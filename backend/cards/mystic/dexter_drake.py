"""Dexter Drake — Mystic Investigator. (07004)
能力：[fast]在你的回合中，丢弃一张你控制的支援卡：从你手牌打出一张不同名称的
支援卡，其费用减1。（每轮限制一次。）
远古印记：+2。你可以将你游戏区域的一张支援卡返回你的手牌。然后，抽取1张卡牌。

简化说明：
- 快速能力实现为公开方法 activate_swap()（参考 skids_otoole 的
  activate_extra_action 模式），由 UI 在玩家选择发动时调用；通过
  INVESTIGATOR_TURN_BEGINS/ENDS 跟踪当前回合调查员（同 skids_otoole）。
- 弃置/打出流程镜像 engine/actions（槽位、费用、CARD_LEAVES_PLAY /
  CARD_ENTERS_PLAY），但卡牌代码无法访问 CardRegistry：被弃支援的 handler
  未注销、新入场支援的卡面能力不注册——引擎缺口（同 ever_vigilant 惯例，
  会话层可补注册）。
- "不同名称"按 card_data.name 比较。
- 远古印记的"你可以……返回手牌"：检定同步流程中无法等待选择，实现为
  scenario.vars["dexter_elder_sign_return"] 预设（公开方法
  choose_elder_sign_return() 设置，须为在场支援的 instance_id）。按官方
  "Then" 规则：只有实际返回了支援才抽1张牌。抽牌直接移动牌库顶到手牌，
  不发 CARD_DRAWN（同 mark_harrigan 惯例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import CardType, ChaosTokenType, GameEvent, TimingPriority
from backend.models.state import CardInstance

PRESET_KEY = "dexter_elder_sign_return"


class DexterDrake(CardImplementation):
    card_id = "dexter_drake"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._used_this_round = False
        self._current_turn_investigator: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def _get_dexter(self, game_state, investigator_id):
        """Return the investigator state iff it is Dexter Drake."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "dexter_drake":
            return None
        return inv

    # ------------------------------------------------------------------
    # [fast] 弃一张支援：从手牌打出不同名称的支援，费用-1（每轮限1次）
    # ------------------------------------------------------------------

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def reset_round_limit(self, ctx):
        self._used_this_round = False

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def on_turn_begins(self, ctx):
        self._current_turn_investigator = ctx.investigator_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.WHEN)
    def on_turn_ends(self, ctx):
        if self._current_turn_investigator == ctx.investigator_id:
            self._current_turn_investigator = None

    def activate_swap(self, game_state, investigator_id,
                      discard_instance_id: str, play_card_id: str) -> bool:
        """[fast] 弃一张你控制的支援：从手牌打出不同名称的支援，费用-1。

        由 UI 在玩家选择发动时调用（每轮限1次，仅限自己回合）。
        """
        inv = self._get_dexter(game_state, investigator_id)
        if inv is None:
            return False
        if self._used_this_round:
            return False
        if self._current_turn_investigator != investigator_id:
            return False

        # 弃置目标：你控制的在场支援
        if discard_instance_id not in inv.play_area:
            return False
        discard_inst = game_state.get_card_instance(discard_instance_id)
        discard_data = (game_state.get_card_data(discard_inst.card_id)
                        if discard_inst else None)
        if discard_data is None or discard_data.type != CardType.ASSET:
            return False

        # 打出目标：手牌中不同名称的支援
        if play_card_id not in inv.hand:
            return False
        play_data = game_state.get_card_data(play_card_id)
        if play_data is None or play_data.type != CardType.ASSET:
            return False
        if play_data.name == discard_data.name:
            return False

        # 槽位检查（先模拟弃置后的空位）
        slot_mgr = getattr(game_state, "slot_managers", {}).get(investigator_id)
        if play_data.slots and slot_mgr is not None:
            saved_traits = slot_mgr.slot_traits.get(discard_instance_id, frozenset())
            slot_mgr.vacate(discard_instance_id)
            fits = slot_mgr.can_play_card(play_data.slots, play_data.traits)
            slot_mgr.occupy(discard_instance_id,
                            discard_inst.slot_used, saved_traits)
            if not fits:
                return False

        cost = max(0, (play_data.cost or 0) - 1)
        if inv.resources < cost:
            return False

        # 弃置旧支援
        if slot_mgr is not None:
            slot_mgr.vacate(discard_instance_id)
        inv.play_area.remove(discard_instance_id)
        inv.discard.append(discard_inst.card_id)
        game_state.cards_in_play.pop(discard_instance_id, None)
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=investigator_id,
                target=discard_instance_id,
                extra={"card_id": discard_inst.card_id},
            ))

        # 打出新支援（费用-1）
        inv.resources -= cost
        inv.hand.remove(play_card_id)
        inst_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=inst_id,
            card_id=play_card_id,
            owner_id=investigator_id,
            controller_id=investigator_id,
            slot_used=list(play_data.slots or []),
        )
        if play_data.uses:
            inst.uses = dict(play_data.uses)
        game_state.cards_in_play[inst_id] = inst
        inv.play_area.append(inst_id)
        if slot_mgr is not None and play_data.slots:
            slot_mgr.occupy(inst_id, play_data.slots, play_data.traits)
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=investigator_id,
                target=inst_id,
                extra={"card_id": play_card_id},
            ))

        self._used_this_round = True
        game_state.log_effect(
            f"🎩 戴克斯特·德雷克：弃置【{game_state.card_name(discard_inst.card_id)}】，"
            f"减1费打出【{game_state.card_name(play_card_id)}】")
        return True

    # ------------------------------------------------------------------
    # 远古印记：+2。可将一张在场支援返回手牌；然后抽1张牌。
    # ------------------------------------------------------------------

    def choose_elder_sign_return(self, game_state, investigator_id,
                                 instance_id: str | None) -> bool:
        """预设远古印记要返回手牌的支援（须为在场支援；None 清除）。由 UI 调用。"""
        inv = self._get_dexter(game_state, investigator_id)
        if inv is None:
            return False
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return False
        if instance_id is None:
            scenario.vars.pop(PRESET_KEY, None)
            return True
        if instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(instance_id)
        data = game_state.get_card_data(inst.card_id) if inst else None
        if data is None or data.type != CardType.ASSET:
            return False
        scenario.vars[PRESET_KEY] = instance_id
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+2；若预设支援仍在场则返回手牌，然后抽1张牌。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_dexter(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(2, "dexter_drake_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        inst_id = scenario.vars.get(PRESET_KEY) if scenario else None
        if not inst_id or inst_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(inst_id)
        data = ctx.game_state.get_card_data(inst.card_id) if inst else None
        if data is None or data.type != CardType.ASSET:
            return

        if scenario is not None:
            scenario.vars.pop(PRESET_KEY, None)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(ctx.investigator_id)
        if slot_mgr is not None:
            slot_mgr.vacate(inst_id)
        inv.play_area.remove(inst_id)
        ctx.game_state.cards_in_play.pop(inst_id, None)
        inv.hand.append(inst.card_id)
        if self._bus is not None:
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_LEAVES_PLAY,
                investigator_id=ctx.investigator_id,
                target=inst_id,
                extra={"card_id": inst.card_id},
            ))

        # "Then, draw 1 card"：实际返回了支援才抽牌
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.game_state.log_effect(
            f"🎩 戴克斯特·德雷克：远古印记，【{ctx.game_state.card_name(inst.card_id)}】"
            "返回手牌并抽1张牌")
