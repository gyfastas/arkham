"""Day of Reckoning (Level 0) — Neutral Treachery, Basic Weakness.
显现：将审判日附着到当前密谋。然后，从混沌袋中搜寻1个[elder_sign]标记
并封印在审判日上。

简化说明：
- "附着到当前密谋"：密谋卡不是 CardInstance，附着关系记入
  scenario.vars["day_of_reckoning"] = {"agenda": <agenda_id>, "sealed": ...}。
- 封印经 bind_chaos_bag() 注入的混沌袋 seal_token 实现（袋中无[elder_sign]
  时不封印）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class DayOfReckoning(CardImplementation):
    card_id = "day_of_reckoning_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "day_of_reckoning_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "day_of_reckoning_lv0" in inv.hand:
            inv.hand.remove("day_of_reckoning_lv0")

        scenario = ctx.game_state.scenario
        agenda = scenario.current_agenda
        agenda_id = None
        if agenda is not None:
            agenda_id = getattr(agenda, "id", None)
        if agenda_id is None and scenario.agenda_deck:
            agenda_id = scenario.agenda_deck[scenario.current_agenda_index]

        sealed = None
        if self._chaos_bag is not None and self._chaos_bag.seal_token(
            ChaosTokenType.ELDER_SIGN
        ):
            sealed = ChaosTokenType.ELDER_SIGN.value

        scenario.vars["day_of_reckoning"] = {
            "agenda": agenda_id,
            "sealed": sealed,
        }
        ctx.extra["day_of_reckoning"] = scenario.vars["day_of_reckoning"]
        ctx.game_state.log_effect(
            f"⚖️ 审判日：附着到密谋 {agenda_id or '（无）'}，"
            f"封印 {sealed or '无（袋中无[elder_sign]）'}")
