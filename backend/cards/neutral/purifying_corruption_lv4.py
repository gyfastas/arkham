"""Purifying Corruption (Level 4) — Neutral Asset. (07273)
[reaction]当你抽取一张非弱点诡计卡时，受到1点伤害和1点恐惧：取消该卡的显现
效果，并在本卡上放置1个资源，作为腐蚀。若本卡上有3个或更多腐蚀，将其从游戏
中移除。
[fast]抽取遭遇牌堆顶牌：治疗1点伤害和1点恐惧，或移除本卡上的1个腐蚀。

简化说明：
- 取消显现沿用 ward_of_protection 惯例：登记 scenario.vars["cancelled_encounter"]，
  由会话层跳过结算。
- 自动触发（官方为玩家选择是否触发反应）：持有者抽非弱点诡计卡时自动支付
  1伤害+1恐惧并取消。
- [fast] 能力由会话层调用 activate()；抽取的遭遇牌经 ENCOUNTER_CARD_DRAWN
  事件走正常流程（若再抽到非弱点诡计会再次触发反应，符合卡面）。
- "从游戏中移除"登记 scenario.vars["removed_from_game"]（abandoned_and_alone 惯例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


class PurifyingCorruption(CardImplementation):
    card_id = "purifying_corruption_lv4"
    activations = [{
        "id": "draw_encounter",
        "label": "[快速] 抽遭遇牌堆顶：治疗1伤害1恐惧或移除1腐蚀",
        "method": "activate",
        # fast：不耗行动
    }]

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def cancel_treachery(self, ctx):
        """抽非弱点诡计卡时：受1伤害1恐惧，取消显现，放置1腐蚀。"""
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return

        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.TREACHERY:
            return
        subtype = getattr(cd, "subtype", "") or ""
        if "weakness" in subtype:
            return

        inv.damage += 1
        inv.horror += 1
        ctx.game_state.scenario.vars["cancelled_encounter"] = card_id
        ctx.extra["purifying_corruption_cancelled"] = card_id
        inst.uses["corruption"] = inst.uses.get("corruption", 0) + 1
        if inst.uses["corruption"] >= 3:
            self._remove_from_game(ctx.game_state, inv)
            ctx.extra["purifying_corruption_removed"] = True

    def activate(self, game_state, investigator_id: str, mode: str = "heal"):
        """[fast] 抽取遭遇牌堆顶牌：治疗1伤害1恐惧，或移除1腐蚀。

        返回抽到的遭遇牌 card_id（None 表示牌堆为空/能力未发动）。
        """
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return None
        if mode == "remove" and inst.uses.get("corruption", 0) <= 0:
            return None

        drawn = None
        if game_state.scenario.encounter_deck:
            drawn = game_state.scenario.encounter_deck.pop(0)
            from backend.engine.event_bus import EventContext
            game_state_event = EventContext(
                game_state=game_state,
                event=GameEvent.ENCOUNTER_CARD_DRAWN,
                investigator_id=investigator_id,
                extra={"card_id": drawn},
            )
            bus = getattr(self, "_bus", None)
            if bus is not None:
                bus.emit(game_state_event)

        if mode == "remove":
            inst.uses["corruption"] -= 1
        else:
            inv.damage = max(0, inv.damage - 1)
            inv.horror = max(0, inv.horror - 1)
        return drawn

    def register(self, bus, instance_id: str) -> None:
        # 保存 bus 句柄以便 activate() 发射 ENCOUNTER_CARD_DRAWN
        self._bus = bus
        super().register(bus, instance_id)

    def _remove_from_game(self, game_state, inv) -> None:
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        game_state.scenario.vars.setdefault("removed_from_game", []).append(
            "purifying_corruption_lv4"
        )
