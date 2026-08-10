"""Ace of Swords (Level 1) — Guardian Asset, Tarot slot. (05023)
你获得+1战斗。
[反应]当游戏开始时，如果宝剑王牌在你的起始手牌中：将它放置入场。

简化说明：
- +1战斗为在场被动（SKILL_VALUE_DETERMINED）。
- "游戏开始时放置入场"：game.setup() 不发出事件，实现为公开方法
  put_into_play()（供会话层在 setup/调度后调用）+ ROUND_BEGINS 懒触发兜底
  （第一轮开始时若仍在手牌则免费入场），与 mark_harrigan 的索菲同一惯例。
  免费入场不占行动、不支付费用，占用塔罗槽。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, SlotType, TimingPriority
from backend.models.state import CardInstance


class AceOfSwords(CardImplementation):
    card_id = "ace_of_swords_lv1"
    persistent_in_hand = True  # 手牌中持续监听（游戏开始时入场的兜底）

    def _in_play(self, game_state, inv) -> bool:
        """本卡是否已在该调查员场上（按 card_id 查找，兼容免费入场路径）。"""
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == self.card_id:
                return True
        return False

    def _put_into_play(self, game_state, inv) -> str | None:
        """从手牌免费放入场上（幂等），返回 instance_id。"""
        # 已在场则不重复
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == self.card_id:
                return iid
        if self.card_id not in inv.hand:
            return None
        inv.hand.remove(self.card_id)
        instance_id = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=self.card_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=[SlotType.TAROT],
        )
        game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        slot_mgr = getattr(game_state, "slot_managers", {}).get(inv.investigator_id)
        if slot_mgr is not None:
            slot_mgr.occupy(instance_id, [SlotType.TAROT], ["tarot"])
        game_state.log_effect("🃏 宝剑王牌：游戏开始时从起始手牌放置入场")
        return instance_id

    def put_into_play(self, game_state, investigator_id: str) -> str | None:
        """游戏开始时若在起始手牌中：放置入场（会话层调用，幂等）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        return self._put_into_play(game_state, inv)

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.WHEN)
    def lazy_setup(self, ctx):
        """第一轮开始时兜底：仍在手牌则放置入场。"""
        if ctx.game_state.scenario.round_number > 1:
            return
        for inv in ctx.game_state.investigators.values():
            if self.card_id in inv.hand:
                self._put_into_play(ctx.game_state, inv)

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """在场时 +1 战斗。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self._in_play(ctx.game_state, inv):
            ctx.modify_amount(1, "ace_of_swords_combat_bonus")
