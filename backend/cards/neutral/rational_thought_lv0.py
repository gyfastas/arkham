"""Rational Thought (Level 0) — Neutral Treachery, Weakness (Carolyn Fern). (05008)
显现 - 将理性思考放置入你的威胁区域，上置4点恐惧。理性思考上的恐惧可以
被视为在卡洛琳·费恩上那样被治疗。若理性思考上没有恐惧，丢弃它。
你不能治疗理性思考以外的卡牌上的恐惧。你不能从卡洛琳·费恩的[reaction]
能力获得资源。

简化说明：
- 治疗通道由 heal_horror() 表达：会话层在治疗卡洛琳的恐惧时可改为治疗
  本卡上的恐惧；清零即丢弃。
- "不能治疗其他卡牌的恐惧"/"不能从反应获资源"由 can_heal_other_horror() /
  can_gain_reaction_resources() 供会话层查询（引擎无通用治疗/能力钩子）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class RationalThought(CardImplementation):
    card_id = "rational_thought_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "rational_thought_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "rational_thought_lv0" in inv.hand:
            inv.hand.remove("rational_thought_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="rational_thought_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ci.horror = 4  # 上置4点恐惧
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def heal_horror(self, game_state, investigator_id, amount: int = 1) -> bool:
        """治疗本卡上的恐惧（视同治疗卡洛琳上的恐惧）；清零时丢弃本卡。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find(game_state, inv)
        if inst is None or inst.horror <= 0:
            return False
        inst.horror = max(0, inst.horror - amount)
        if inst.horror == 0:
            inv.threat_area.remove(inst.instance_id)
            game_state.cards_in_play.pop(inst.instance_id, None)
            inv.discard.append("rational_thought_lv0")
        return True

    def can_heal_other_horror(self, game_state, investigator_id) -> bool:
        """本卡在场时：不能治疗理性思考以外卡牌上的恐惧。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        return self._find(game_state, inv) is None

    def can_gain_reaction_resources(self, game_state, investigator_id) -> bool:
        """本卡在场时：不能从卡洛琳·费恩的[reaction]能力获得资源。"""
        return self.can_heal_other_horror(game_state, investigator_id)

    @staticmethod
    def _find(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "rational_thought_lv0":
                return inst
        return None
