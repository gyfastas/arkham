"""Joe Diamond — Seeker Investigator.
能力：<b>强制</b> - 在调查阶段开始时：翻开你的直觉牌组顶部的卡牌。本阶段结束前，
你可以以-2费用打出该卡牌，如同其为你的手牌。如果当本阶段结束时该卡牌未被打出，
将其混洗回你的直觉牌组。
远古印记：+1。你可以将你弃牌堆的1张[[洞察]]事件卡移动到你直觉牌组底部。

牌组构建附加需求（部分实现）：设置期间从牌组中选择11张[[洞察]]事件（其中必须
包括悬案）混洗为单独的"直觉牌组"。

简化说明：
- 直觉牌组存放在 scenario.vars["hunch_deck_{investigator_id}"]（顶=index 0），
  翻开的牌存放在 scenario.vars["hunch_revealed_{investigator_id}"]（与
  sefina_rousseau 的 beneath 约定同源）。
- 设置时组建：Game.setup() 激活实现后不发事件，因此在 setup 阶段首次
  CARD_DRAWN 时懒组建（首张已抽的开局牌若为洞察事件则留在手牌——遗留
  简化；引擎 setup 抽牌流程不可拦截）。自动组建取牌库中前11张洞察事件
  （含悬案时优先放入，官方为玩家选择11张）并混洗。会话层/测试可在 setup
  前经 scenario.vars 预设直觉牌组以跳过自动组建（公开方法
  setup_hunch_deck() 亦可显式组建）。
- 以-2费用打出翻开的牌：公开方法 activate_play_hunch()（由 UI 调用），
  复刻 ActionResolver._play_event 流程（临时注册实现、CARD_PLAYED、入弃
  牌堆、ROUND_ENDS 清理）；视为一次打出行动：非快速牌扣1行动，并经
  action_resolver 结算趁乱攻击。
- 阶段结束未打出：混洗回直觉牌组（random.shuffle；官方"混洗回"）。
- 远古印记移回洞察事件：scenario.vars["joe_diamond_hunch_choice"] 可预设
  弃牌堆中的目标，缺省取弃牌堆中第一张洞察事件（官方为玩家选择且可放弃）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, Phase, TimingPriority,
)

HUNCH_DECK_SIZE = 11
HUNCH_COST_DISCOUNT = 2


def hunch_deck_key(investigator_id: str) -> str:
    return f"hunch_deck_{investigator_id}"


def hunch_revealed_key(investigator_id: str) -> str:
    return f"hunch_revealed_{investigator_id}"


class JoeDiamond(CardImplementation):
    card_id = "joe_diamond"

    activations = [{
        "id": "play_hunch",
        "label": "以-2费用打出翻开的直觉牌",
        "method": "activate_play_hunch",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._hunch_formed = False

    def _get_joe(self, game_state, investigator_id):
        """Return the investigator state iff it is Joe Diamond."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "joe_diamond":
            return None
        return inv

    def _joe_in_game(self, game_state):
        for inv in game_state.investigators.values():
            card_data = getattr(inv, "card_data", None)
            if card_data is not None and card_data.id == "joe_diamond":
                return inv
        return None

    def _is_insight_event(self, game_state, card_id) -> bool:
        cd = game_state.get_card_data(card_id)
        return (
            cd is not None
            and cd.type == CardType.EVENT
            and "insight" in (cd.traits or [])
        )

    def setup_hunch_deck(self, game_state, investigator_id,
                         card_ids=None) -> list[str]:
        """设置时组建直觉牌组（幂等）。card_ids 缺省时自动取牌库中前11张
        洞察事件（悬案优先）并混洗。返回组建后的直觉牌组。"""
        inv = self._get_joe(game_state, investigator_id)
        scenario = getattr(game_state, "scenario", None)
        if inv is None or scenario is None:
            return []
        key = hunch_deck_key(investigator_id)
        if self._hunch_formed or key in scenario.vars:
            self._hunch_formed = True
            return scenario.vars.get(key, [])

        if card_ids is None:
            insight = [c for c in inv.deck if self._is_insight_event(game_state, c)]
            chosen = []
            if "unsolved_case_lv0" in insight:
                chosen.append("unsolved_case_lv0")
            for c in insight:
                if len(chosen) >= HUNCH_DECK_SIZE:
                    break
                if c not in chosen:
                    chosen.append(c)
            card_ids = chosen
            random.shuffle(card_ids)

        for c in card_ids:
            if c in inv.deck:
                inv.deck.remove(c)
        scenario.vars[key] = list(card_ids)
        self._hunch_formed = True
        game_state.log_effect(
            f"🔍 乔·戴蒙德：组建直觉牌组（{len(card_ids)}张洞察事件）"
        )
        return scenario.vars[key]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def form_hunch_deck_on_setup(self, ctx):
        """setup 阶段首次抽牌时懒组建直觉牌组。"""
        if self._hunch_formed:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.SETUP:
            return
        inv = self._get_joe(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        self.setup_hunch_deck(ctx.game_state, ctx.investigator_id)

    @on_event(GameEvent.INVESTIGATION_PHASE_BEGINS, priority=TimingPriority.FORCED)
    def reveal_hunch_card(self, ctx):
        """强制 - 调查阶段开始时：翻开直觉牌组顶部的卡牌。"""
        inv = self._joe_in_game(ctx.game_state)
        scenario = getattr(ctx.game_state, "scenario", None)
        if inv is None or scenario is None:
            return
        deck = scenario.vars.get(hunch_deck_key(inv.investigator_id)) or []
        rkey = hunch_revealed_key(inv.investigator_id)
        if scenario.vars.get(rkey):
            return  # 已有翻开的牌（非正常流程，防御）
        if not deck:
            return
        revealed = deck.pop(0)
        scenario.vars[rkey] = revealed
        ctx.game_state.log_effect(
            f"🔍 乔·戴蒙德：翻开直觉牌【{ctx.game_state.card_name(revealed)}】"
            f"（本阶段可以-2费用打出）"
        )

    def activate_play_hunch(self, game, investigator_id) -> bool:
        """以-2费用打出翻开的直觉牌（如同手牌）。由 UI 调用。"""
        game_state = game.state
        inv = self._get_joe(game_state, investigator_id)
        scenario = getattr(game_state, "scenario", None)
        if inv is None or scenario is None:
            return False
        rkey = hunch_revealed_key(investigator_id)
        revealed = scenario.vars.get(rkey)
        if not revealed:
            return False
        cd = game_state.get_card_data(revealed)
        if cd is None or cd.type != CardType.EVENT:
            return False

        is_fast = bool(cd.fast)
        if not is_fast and inv.actions_remaining < 1:
            return False
        cost = max(0, (cd.cost or 0) - HUNCH_COST_DISCOUNT)
        if inv.resources < cost:
            return False

        scenario.vars[rkey] = None
        inv.resources -= cost
        if not is_fast:
            inv.actions_remaining -= 1

        from backend.engine.event_bus import EventContext
        if cost > 0:
            game.event_bus.emit(EventContext(
                game_state=game_state,
                event=GameEvent.RESOURCES_SPENT,
                investigator_id=investigator_id,
                amount=cost,
            ))

        # 复刻 ActionResolver._play_event：临时注册实现，ROUND_ENDS 清理
        temp_instance_id = game_state.next_instance_id()
        cleanup_entry = None
        if game.card_registry:
            game.card_registry.activate_card(
                revealed, temp_instance_id, game.event_bus,
                chaos_bag=game.chaos_bag)

            def _cleanup(c):
                game.card_registry.deactivate_card(temp_instance_id, game.event_bus)
                if cleanup_entry is not None:
                    game.event_bus.unregister(cleanup_entry)

            cleanup_entry = game.event_bus.register(
                event=GameEvent.ROUND_ENDS,
                handler=_cleanup,
                priority=TimingPriority.AFTER,
                card_instance_id=temp_instance_id,
            )

        game.event_bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CARD_PLAYED,
            investigator_id=investigator_id,
            source=temp_instance_id,
            extra={"card_id": revealed},
        ))
        inv.discard.append(revealed)

        # 视为打出行动：结算趁乱攻击（快速牌不扣行动也不引发）
        if not is_fast:
            game.action_resolver._resolve_attacks_of_opportunity(investigator_id)

        game_state.log_effect(
            f"🔍 乔·戴蒙德：以-2费用打出直觉牌"
            f"【{game_state.card_name(revealed)}】"
        )
        return True

    @on_event(GameEvent.INVESTIGATION_PHASE_ENDS, priority=TimingPriority.AFTER)
    def shuffle_back_unplayed(self, ctx):
        """阶段结束时仍未打出：混洗回直觉牌组。"""
        inv = self._joe_in_game(ctx.game_state)
        scenario = getattr(ctx.game_state, "scenario", None)
        if inv is None or scenario is None:
            return
        rkey = hunch_revealed_key(inv.investigator_id)
        revealed = scenario.vars.get(rkey)
        if not revealed:
            return
        scenario.vars[rkey] = None
        deck = scenario.vars.setdefault(hunch_deck_key(inv.investigator_id), [])
        deck.append(revealed)
        random.shuffle(deck)
        ctx.game_state.log_effect(
            f"🔍 乔·戴蒙德：【{ctx.game_state.card_name(revealed)}】混洗回直觉牌组"
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。将弃牌堆中1张洞察事件移到直觉牌组底部。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_joe(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "joe_diamond_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return
        candidates = [
            c for c in inv.discard if self._is_insight_event(ctx.game_state, c)
        ]
        if not candidates:
            return
        preset = scenario.vars.get("joe_diamond_hunch_choice")
        chosen = preset if preset in candidates else candidates[0]
        inv.discard.remove(chosen)
        scenario.vars.setdefault(
            hunch_deck_key(ctx.investigator_id), []).append(chosen)
        ctx.game_state.log_effect(
            f"🔍 乔·戴蒙德：远古印记，【{ctx.game_state.card_name(chosen)}】"
            f"移到直觉牌组底部"
        )
