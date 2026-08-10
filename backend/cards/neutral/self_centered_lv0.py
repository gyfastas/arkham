"""Self-Centered (Level 0) — Neutral Treachery, Basic Weakness. (06035)
仅限多人游戏。
显现 - 将以自我为中心放置入你的威胁区域。
你不能向其他调查员的技能检定投入卡牌，也不能以玩家卡效果影响其他调查员
（导致伤害或恐惧的方面除外）。
[action][action]：丢弃以自我为中心。

简化说明：
- 投入/影响限制由 can_commit_to_others() / can_affect_others() 供会话层
  查询（引擎投入与效果结算无卡牌级前置过滤钩子）。
- "仅限多人游戏"为构筑限制，由卡组校验负责。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class SelfCentered(CardImplementation):
    card_id = "self_centered_lv0"
    activations = [{"id": "discard", "label": "[行动×2] 丢弃以自我为中心", "method": "activate_discard", "actions": 2}]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "self_centered_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "self_centered_lv0" in inv.hand:
            inv.hand.remove("self_centered_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="self_centered_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.threat_area.append(inst_id)

    def can_commit_to_others(self, game_state, investigator_id) -> bool:
        """本卡在威胁区时：不能向其他调查员的检定投入卡牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        return self._find(game_state, inv) is None

    def can_affect_others(self, game_state, investigator_id) -> bool:
        """本卡在威胁区时：不能以玩家卡效果影响其他调查员（伤害/恐惧除外）。"""
        return self.can_commit_to_others(game_state, investigator_id)

    def activate_discard(self, game_state, investigator_id) -> bool:
        """[action][action]：丢弃以自我为中心。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find(game_state, inv)
        if inst is None:
            return False
        inv.threat_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.discard.append("self_centered_lv0")
        return True

    @staticmethod
    def _find(game_state, inv):
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "self_centered_lv0":
                return inst
        return None
