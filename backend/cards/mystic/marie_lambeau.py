"""Marie Lambeau — Mystic Investigator.
能力：只要你控制的卡牌上有至少1个毁灭标记，你可以在自己的回合期间进行一个
额外行动，该额外行动只能用于打出[[法术]]卡牌或启动[[法术]][action]能力。
远古印记：+1。你可以在你控制的一张卡牌上增加或移除1个毁灭标记。

简化说明：
- 额外行动在 INVESTIGATOR_TURN_BEGINS 时授予（actions_remaining += 1）；
  "只能用于打出/启动法术"的限制无法在不修改 engine/actions.py 行动扣减
  流程的前提下强制执行——引擎缺口，当前额外行动不限制用途。
- "你控制的卡牌上的毁灭标记"统计 play_area 中 CardInstance.doom；调查员卡
  本身无 doom 字段（引擎未建模），不计入——引擎缺口。
- 远古印记的"可以增加或移除1个毁灭标记"为可选玩家选择：优先读取一次性预设
  scenario.vars["marie_lambeau_doom_choice"]（{"instance_id": ..., "delta": ±1}，
  结算后弹出）；无预设时设置 pending_choice（kind="marie_lambeau_doom"），
  由 UI 调用公开方法 resolve_doom_choice() 结算。
- 毁灭标记加减直接改 CardInstance.doom（total_doom_in_play 已统计该字段，
  议程阈值联动正确）；移除时下限为0。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class MarieLambeau(CardImplementation):
    card_id = "marie_lambeau"

    def _get_marie(self, game_state, investigator_id):
        """Return the investigator state iff it is Marie Lambeau."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "marie_lambeau":
            return None
        return inv

    def _doomed_cards(self, game_state, inv):
        """玛丽控制的在场卡牌实例列表。"""
        return [
            inst for inst_id in inv.play_area
            if (inst := game_state.get_card_instance(inst_id)) is not None
        ]

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def grant_extra_action(self, ctx):
        """控制的卡牌上有毁灭标记时，本回合获得1个额外行动（限制未强制，见文件头）。"""
        inv = self._get_marie(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        doom = sum(inst.doom for inst in self._doomed_cards(ctx.game_state, inv))
        if doom < 1:
            return
        inv.actions_remaining += 1
        ctx.game_state.log_effect("🎤 玛丽·朗博：控制的卡牌上有毁灭标记，获得1个额外行动")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。可以在你控制的一张卡牌上增加或移除1个毁灭标记。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_marie(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "marie_lambeau_elder_sign")

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return

        preset = scenario.vars.pop("marie_lambeau_doom_choice", None)
        if preset:
            self.resolve_doom_choice(
                ctx.game_state, ctx.investigator_id,
                preset.get("instance_id"), preset.get("delta", 0),
            )
            return

        options = [{"id": "decline", "label": "不触发"}]
        for inst in self._doomed_cards(ctx.game_state, inv):
            name = ctx.game_state.card_name(inst.card_id)
            options.append({"id": f"add:{inst.instance_id}",
                            "label": f"在【{name}】上增加1个毁灭标记"})
            if inst.doom > 0:
                options.append({"id": f"remove:{inst.instance_id}",
                                "label": f"从【{name}】上移除1个毁灭标记"})
        scenario.vars["pending_choice"] = {
            "kind": "marie_lambeau_doom",
            "investigator_id": ctx.investigator_id,
            "prompt": "<b>玛丽·朗博</b>：远古印记，是否在你控制的一张卡牌上增加或移除1个毁灭标记？",
            "options": options,
        }

    def resolve_doom_choice(self, game_state, investigator_id,
                            instance_id: str | None, delta: int = 0) -> bool:
        """结算远古印记的毁灭标记加减。由 UI 在玩家选择后调用（delta: +1/-1）。"""
        inv = self._get_marie(game_state, investigator_id)
        if inv is None:
            return False

        scenario = getattr(game_state, "scenario", None)
        if scenario is not None:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == "marie_lambeau_doom":
                scenario.vars.pop("pending_choice", None)

        if instance_id is None or delta not in (1, -1):
            return False
        inst = game_state.get_card_instance(instance_id)
        if inst is None or instance_id not in inv.play_area:
            return False

        if delta > 0:
            inst.doom += 1
            game_state.log_effect(
                f"🎤 玛丽·朗博：在【{game_state.card_name(inst.card_id)}】上增加1个毁灭标记"
            )
        else:
            if inst.doom < 1:
                return False
            inst.doom -= 1
            game_state.log_effect(
                f"🎤 玛丽·朗博：从【{game_state.card_name(inst.card_id)}】上移除1个毁灭标记"
            )
        return True
