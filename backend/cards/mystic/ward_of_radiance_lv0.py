"""Ward of Radiance (Level 0) — Mystic Event. (07031)
快速。你所在地点的一位调查员抽取一张非弱点诡计卡时打出。
从混乱袋随机揭示5个混乱标记。如果揭示了[bless]或[elder_sign]标记，
取消该诡计卡的显现效果。

简化说明：
- 自动触发（同 ward_of_protection / a_test_of_will 惯例）：持有者与你
  同地点即可，费用0；标记 scenario.vars["cancelled_encounter"]，由会话层
  跳过显现结算。
- 揭示5个标记为无放回抽样（bag._rng.sample），揭示后标记归还袋中
  （袋不做任何变动）。混沌袋经 bind_chaos_bag 注入（生产中在手的实现
  注册路径与 ward_of_protection 相同，为已知引擎/会话缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import find_holder
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)
from backend.models.state import is_weakness_card

_CANCEL_TOKENS = {ChaosTokenType.BLESS, ChaosTokenType.ELDER_SIGN}


class WardOfRadiance(CardImplementation):
    card_id = "ward_of_radiance_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def maybe_cancel_treachery(self, ctx):
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.TREACHERY or is_weakness_card(cd):
            return
        # 持有者须与抽牌者同地点
        holder = find_holder(ctx.game_state, self.card_id)
        drawer = ctx.game_state.get_investigator(ctx.investigator_id)
        if holder is None or drawer is None \
                or holder.location_id != drawer.location_id:
            return

        # 自动打出（费用0）
        holder.hand.remove(self.card_id)
        holder.discard.append(self.card_id)

        # 揭示5个标记（无放回；揭示后归还，袋不变动）
        revealed: list[ChaosTokenType] = []
        if self._bag is not None and self._bag.tokens:
            revealed = self._bag._rng.sample(
                self._bag.tokens, min(5, len(self._bag.tokens)))
        ctx.extra["ward_of_radiance_revealed"] = [t.value for t in revealed]

        if any(t in _CANCEL_TOKENS for t in revealed):
            ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
            ctx.extra["ward_of_radiance_cancelled"] = card_id
            ctx.game_state.log_effect(
                f"✨ 光辉结界：揭示 {[t.value for t in revealed]}，"
                f"取消【{ctx.game_state.card_name(card_id)}】的显现效果")
        else:
            ctx.game_state.log_effect(
                f"✨ 光辉结界：揭示 {[t.value for t in revealed]}，未取消")
