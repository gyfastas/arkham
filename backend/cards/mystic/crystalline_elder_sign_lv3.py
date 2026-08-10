"""Crystalline Elder Sign (Level 3) — Mystic Asset, Accessory slot. (04235)
封印（+1或[elder_sign]）。
你获得+1[willpower]、+1[intellect]、+1[combat]和+1[agility]。

简化说明：
- 封印目标二选一：自动优先封印+1（袋中没有+1时封印[elder_sign]）。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时封印效果跳过（技能加值不受影响）。
- 离场时被封印的标记返还袋中。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority


class CrystallineElderSign(CardImplementation):
    card_id = "crystalline_elder_sign_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._sealed_token: ChaosTokenType | None = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_on_enter(self, ctx):
        """入场：封印（+1或[elder_sign]），自动优先+1。"""
        if ctx.target != self.instance_id or self._chaos_bag is None:
            return
        for token in (ChaosTokenType.PLUS_1, ChaosTokenType.ELDER_SIGN):
            if self._chaos_bag.seal_token(token):
                self._sealed_token = token
                ctx.extra["crystalline_elder_sign_sealed"] = token.value
                ctx.game_state.log_effect(f"💠 远古印记结晶：封印[{token.value}]")
                return

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        """离场：返还被封印的标记。"""
        if ctx.target != self.instance_id:
            return
        if self._sealed_token is not None and self._chaos_bag is not None:
            self._chaos_bag.release_token(self._sealed_token)
            self._sealed_token = None

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """+1意志、+1智力、+1战斗、+1敏捷。"""
        if ctx.skill_type not in (
            Skill.WILLPOWER, Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY,
        ):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "crystalline_elder_sign_bonus")
