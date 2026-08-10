"""Carolyn Fern — Guardian Investigator.
能力：[reaction]在你一张卡牌效果治愈一位调查员或一张[[盟友]]支援卡的恐惧后：
被治愈的卡牌的控制者获得1资源。
远古印记：+1。你可以治愈你所在地点的一位调查员或一张[[盟友]]支援卡的1点恐惧。

简化说明：
- 引擎无"治愈恐惧"事件（引擎缺口，hypnotic_therapy_lv0 已注明同一缺口），
  反应能力实现为公开方法 notify_horror_healed()，由会话层在卡洛琳的卡牌
  效果治愈恐惧结算后调用（target 二选一：调查员或盟友实例）。"你的一张
  卡牌效果"按治愈来源的控制者是卡洛琳校验。官方文本无次数限制。
- 远古印记的治愈目标：简化为自动选择——scenario.vars
  ["carolyn_fern_elder_target"] 可预设（调查员 id 或盟友 instance_id）；
  缺省按玩家顺序取她所在地点第一位有恐惧的调查员，否则第一张有恐惧的
  盟友（其控制者须在她所在地点）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class CarolynFern(CardImplementation):
    card_id = "carolyn_fern"

    def _get_carolyn(self, game_state, investigator_id):
        """Return the investigator state iff it is Carolyn Fern."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "carolyn_fern":
            return None
        return inv

    def _is_ally_instance(self, game_state, instance_id) -> bool:
        inst = game_state.get_card_instance(instance_id)
        if inst is None:
            return False
        cd = game_state.get_card_data(inst.card_id)
        return cd is not None and "ally" in (cd.traits or [])

    def notify_horror_healed(self, game_state, healer_controller_id,
                             target_investigator_id=None,
                             target_instance_id=None) -> bool:
        """[reaction] 卡洛琳的卡牌效果治愈恐惧后：被治愈卡牌的控制者获得1资源。

        由会话层在治愈结算后调用（引擎无治愈事件，见模块说明）。
        """
        if self._get_carolyn(game_state, healer_controller_id) is None:
            return False
        controller_id = None
        if target_investigator_id is not None:
            if game_state.get_investigator(target_investigator_id) is None:
                return False
            controller_id = target_investigator_id
        elif target_instance_id is not None:
            inst = game_state.get_card_instance(target_instance_id)
            if inst is None or not self._is_ally_instance(game_state, target_instance_id):
                return False
            controller_id = inst.controller_id
        else:
            return False
        controller = game_state.get_investigator(controller_id)
        if controller is None:
            return False
        controller.resources += 1
        game_state.log_effect(
            f"🛋️ 卡洛琳·弗恩：治愈恐惧，{controller_id} 获得1资源"
        )
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。治愈所在地点一位调查员或一张盟友的1点恐惧。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_carolyn(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "carolyn_fern_elder_sign")

        game_state = ctx.game_state
        scenario = getattr(game_state, "scenario", None)
        preset = scenario.vars.get("carolyn_fern_elder_target") \
            if scenario is not None else None

        # 候选目标：她所在地点的调查员与盟友（带恐惧）
        def _inv_horror(cand_id):
            cand = game_state.get_investigator(cand_id)
            return (
                cand is not None
                and cand.location_id == inv.location_id
                and cand.horror > 0
            )

        def _ally_horror(inst_id):
            inst = game_state.get_card_instance(inst_id)
            if inst is None or inst.horror <= 0:
                return False
            if not self._is_ally_instance(game_state, inst_id):
                return False
            controller = game_state.get_investigator(inst.controller_id)
            return controller is not None \
                and controller.location_id == inv.location_id

        healed = None
        if preset is not None:
            if _inv_horror(preset) or _ally_horror(preset):
                healed = preset
        if healed is None:
            for cand_id in game_state.player_order:
                if _inv_horror(cand_id):
                    healed = cand_id
                    break
        if healed is None:
            for inst_id, inst in game_state.cards_in_play.items():
                if _ally_horror(inst_id):
                    healed = inst_id
                    break

        if healed is None:
            return
        target_inv = game_state.get_investigator(healed)
        if target_inv is not None:
            target_inv.horror -= 1
        else:
            game_state.get_card_instance(healed).horror -= 1
        game_state.log_effect("🛋️ 卡洛琳·弗恩：远古印记，治愈1点恐惧")
