"""The Moon • XVIII (Level 1) — Rogue Asset, Tarot slot. (05031)
你获得+1[agility]。
[reaction] 在游戏开始时，如果月亮·XVIII在你起始手牌中：将其放置入场。

简化说明：
- 游戏开始时的入场由会话层在起始手牌结算时调用
  put_into_play_at_game_begin()（引擎无 GAME_BEGINS 事件——缺口，
  同 ace_of_rods 模式）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TheMoonXVIII(CardImplementation):
    card_id = "the_moon_•_xviii_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        """+1敏捷（在场时持续生效）。"""
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "the_moon_agility")

    def put_into_play_at_game_begin(self, game_state, investigator_id) -> bool:
        """[reaction] 游戏开始时在起始手牌中：放置入场（会话层调用，免费）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return False
        inv.hand.remove(self.card_id)
        from backend.models.state import CardInstance
        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id=self.card_id,
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)
        game_state.log_effect("🌙 月亮·XVIII：游戏开始时从起始手牌放置入场")
        return True
