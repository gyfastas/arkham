"""Burden of Destiny (Level 0) — Neutral Treachery, Weakness.
显现：你必须（二选一）：
- 将你控制的1张戒律翻至其[[Broken]]面。本轮内不能将其翻回。
- 受到1点伤害和1点恐惧。

简化说明：
- 二选一自动判定：控制着未破损的戒律（discipline_*）则翻开第一张；
  否则受到1点伤害和1点恐惧（官方为玩家选择）。
- 戒律的破损状态记入 scenario.vars["discipline_broken_{instance_id}"] =
  破损时的轮数（discipline_lv0 实现读取同一键；"本轮内不能翻回"按轮数
  判定）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BurdenOfDestiny(CardImplementation):
    card_id = "burden_of_destiny_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "burden_of_destiny_lv0":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "burden_of_destiny_lv0" in inv.hand:
            inv.hand.remove("burden_of_destiny_lv0")

        # 查找控制的未破损戒律
        discipline_inst_id = None
        for inst_id in list(inv.play_area):
            inst = game_state.get_card_instance(inst_id)
            if inst is None or not inst.card_id.startswith("discipline_"):
                continue
            key = f"discipline_broken_{inst_id}"
            if key not in game_state.scenario.vars:
                discipline_inst_id = inst_id
                break

        if discipline_inst_id is not None:
            round_number = game_state.scenario.round_number
            game_state.scenario.vars[
                f"discipline_broken_{discipline_inst_id}"] = round_number
            ctx.extra["burden_of_destiny_flipped"] = discipline_inst_id
            game_state.log_effect("⛓️ 命运重担：戒律被翻至破损面")
        else:
            inv.damage += 1  # 直接伤害/恐惧（不分配）
            inv.horror += 1
            ctx.extra["burden_of_destiny_suffered"] = True
            game_state.log_effect("⛓️ 命运重担：受到1点伤害和1点恐惧")

        inv.discard.append("burden_of_destiny_lv0")
