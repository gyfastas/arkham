"""Akachi Onyele — Mystic Investigator.
能力：你带有"使用(充能)"的支援卡入场时带有额外1点充能。
远古印记：+1。你控制的一张带有"使用(充能)"的支援卡增加1点充能。

简化说明：
- "带有使用(充能)"按卡牌数据的 uses 含 "charges" 键判定（如 shrivelling 的
  uses={"charges": 4}）；ammo/supply 等其他用途类型不受影响。
- 入场加充能挂 CARD_ENTERS_PLAY（引擎在 _play_asset 中先初始化 uses 再发事件，
  因此事件处理器里 +1 即为最终充能）。
- 远古印记的"你控制的一张……支援卡"：同步检定流程中无法等待玩家选择，
  简化为自动选择场上第一张带充能的支援卡；可在触发前设置
  scenario.vars["akachi_onyele_charge_target"] = instance_id 指定目标
  （与 agnes_baker_target 同一惯例）。没有符合条件的支援卡时只保留 +1。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, TimingPriority,
)


class AkachiOnyele(CardImplementation):
    card_id = "akachi_onyele"

    def _get_akachi(self, game_state, investigator_id):
        """Return the investigator state iff it is Akachi Onyele."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "akachi_onyele":
            return None
        return inv

    @staticmethod
    def _has_charges(card_data) -> bool:
        return (
            card_data is not None
            and card_data.type == CardType.ASSET
            and "charges" in (card_data.uses or {})
        )

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def bonus_charge_on_enter(self, ctx):
        """你带有"使用(充能)"的支援卡入场时带有额外1点充能。"""
        inv = self._get_akachi(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        inst = ctx.game_state.get_card_instance(ctx.target) if ctx.target else None
        if inst is None or inst.controller_id != inv.investigator_id:
            return
        card_data = ctx.game_state.get_card_data(inst.card_id)
        if not self._has_charges(card_data):
            return
        inst.uses["charges"] = inst.uses.get("charges", 0) + 1
        ctx.game_state.log_effect(
            f"🔮 阿喀琦·奥耶莉：【{ctx.game_state.card_name(inst.card_id)}】"
            "入场时额外+1充能"
        )

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。你控制的一张带充能支援卡+1充能（简化：自动选第一张）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_akachi(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "akachi_onyele_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        override = None
        if scenario is not None:
            override = scenario.vars.pop("akachi_onyele_charge_target", None)

        target = None
        if override is not None and override in inv.play_area:
            inst = ctx.game_state.get_card_instance(override)
            if inst is not None and self._has_charges(
                ctx.game_state.get_card_data(inst.card_id)
            ):
                target = inst
        if target is None:
            for inst_id in inv.play_area:
                inst = ctx.game_state.get_card_instance(inst_id)
                if inst is None:
                    continue
                if self._has_charges(ctx.game_state.get_card_data(inst.card_id)):
                    target = inst
                    break
        if target is not None:
            target.uses["charges"] = target.uses.get("charges", 0) + 1
            ctx.game_state.log_effect(
                f"🔮 阿喀琦·奥耶莉：远古印记，"
                f"【{ctx.game_state.card_name(target.card_id)}】+1充能"
            )
