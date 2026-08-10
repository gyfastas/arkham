"""Sefina Rousseau — Rogue Investigator.
能力：强制 - 在你将要抽取起始手牌时：改为抽取13张卡牌。选择最多5张事件卡放在
本卡牌下，并保留8张卡牌作为你的起始手牌。丢弃其余卡牌。(你不能换牌。)
[action]：选择并抽取本卡牌下方的一张事件卡。不会引起趁乱攻击。
远古印记：+3。你可以选择并抽取本卡牌下的一张事件卡。

简化说明：
- "赛菲娜·卢梭下的卡牌"存放在 scenario.vars["beneath_{investigator_id}"]
  （与 stars_of_hyades_lv0 / the_painted_world_lv0 共用的既定约定）。
- 开局强制能力：Game.setup() 的抽牌流程固定抽5张且不可拦截，实现为在 setup
  阶段第5次 CARD_DRAWN 时补抽8张（合计13张），然后自动结算：按手牌顺序选择
  前5张事件卡置于赛菲娜之下（官方为玩家选择，可少于5张），保留其余卡牌中的
  前8张，弃掉剩余。补抽直接移动牌库顶到手牌、不发 CARD_DRAWN，且未对补抽中
  的弱点做搁置处理（引擎 setup 的弱点搁置只覆盖前5张）——遗留简化。
- "你不能换牌"：mulligan 在会话层结算，引擎无拦截钩子——引擎缺口，
  会话层须跳过赛菲娜的调度。
- [action] 能力实现为公开方法 activate_draw_beneath()（参考 ashcan_pete 的
  activate_ready_asset 模式），直接扣1行动、不经 perform_action，因此天然
  不引起趁乱攻击；由 UI 在玩家选择发动时调用，card_id 参数为玩家所选事件，
  缺省自动取赛菲娜下的第一张事件。
- 远古印记的"你可以……抽取"：同步检定流程中无法等待玩家选择，简化为自动
  抽取赛菲娜下的第一张事件（官方为玩家选择且可放弃）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, Phase, TimingPriority,
)

OPENING_HAND_DRAW = 5
EXTRA_DRAW = 8  # 13 = 5（引擎 setup 抽）+ 8（本实现补抽）
MAX_BENEATH = 5
KEEP = 8


def beneath_key(investigator_id: str) -> str:
    return f"beneath_{investigator_id}"


class SefinaRousseau(CardImplementation):
    card_id = "sefina_rousseau"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._setup_draws = 0
        self._opening_hand_resolved = False

    def _get_sefina(self, game_state, investigator_id):
        """Return the investigator state iff it is Sefina Rousseau."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "sefina_rousseau":
            return None
        return inv

    def _events_beneath(self, game_state, investigator_id) -> list[str]:
        """赛菲娜之下的事件卡 id 列表（保持放入顺序）。"""
        scenario = getattr(game_state, "scenario", None)
        if scenario is None:
            return []
        beneath = scenario.vars.get(beneath_key(investigator_id), [])
        return [
            cid for cid in beneath
            if (cd := game_state.get_card_data(cid)) is not None
            and cd.type == CardType.EVENT
        ]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def opening_hand(self, ctx):
        """强制 - 将要抽起始手牌时改为抽13张：补抽后自动结算赛菲娜之下/保留/弃置。"""
        if self._opening_hand_resolved:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None or scenario.current_phase != Phase.SETUP:
            return
        inv = self._get_sefina(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        self._setup_draws += 1
        if self._setup_draws < OPENING_HAND_DRAW:
            return
        self._opening_hand_resolved = True

        # 补抽8张（合计13张；引擎已抽5张）
        for _ in range(EXTRA_DRAW):
            if not inv.deck:
                break
            inv.hand.append(inv.deck.pop(0))

        # 自动结算：前5张事件卡置于赛菲娜之下
        beneath = scenario.vars.setdefault(beneath_key(inv.investigator_id), [])
        events = [
            cid for cid in inv.hand
            if (cd := ctx.game_state.get_card_data(cid)) is not None
            and cd.type == CardType.EVENT
        ][:MAX_BENEATH]
        for cid in events:
            inv.hand.remove(cid)
            beneath.append(cid)

        # 保留前8张，弃掉其余
        while len(inv.hand) > KEEP:
            inv.discard.append(inv.hand.pop())

        ctx.game_state.log_effect(
            f"🎨 赛菲娜·卢梭：抽13张，{len(events)}张事件置于赛菲娜之下，"
            f"保留{len(inv.hand)}张，弃掉其余"
        )

    def activate_draw_beneath(self, game_state, investigator_id,
                              card_id: str | None = None) -> bool:
        """[action]：选择并抽取赛菲娜之下的一张事件卡（不引起趁乱攻击）。由 UI 调用。"""
        inv = self._get_sefina(game_state, investigator_id)
        if inv is None or inv.actions_remaining < 1:
            return False
        events = self._events_beneath(game_state, investigator_id)
        if not events:
            return False
        chosen = card_id if card_id is not None else events[0]
        if chosen not in events:
            return False

        scenario = game_state.scenario
        scenario.vars[beneath_key(investigator_id)].remove(chosen)
        inv.hand.append(chosen)
        inv.actions_remaining -= 1
        game_state.log_effect(
            f"🎨 赛菲娜·卢梭：从赛菲娜之下抽取【{game_state.card_name(chosen)}】"
        )
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+3。自动抽取赛菲娜之下的第一张事件（简化：官方为玩家选择）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_sefina(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(3, "sefina_rousseau_elder_sign")

        events = self._events_beneath(ctx.game_state, ctx.investigator_id)
        if events:
            chosen = events[0]
            ctx.game_state.scenario.vars[beneath_key(ctx.investigator_id)].remove(chosen)
            inv.hand.append(chosen)
            ctx.game_state.log_effect(
                f"🎨 赛菲娜·卢梭：远古印记，从赛菲娜之下抽取"
                f"【{ctx.game_state.card_name(chosen)}】"
            )
