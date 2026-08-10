"""Sophie (Level 0) — Neutral Asset, Signature (Mark Harrigan). 双面卡。
正面：索菲不能离场。[fast]受到1点直接伤害：本次技能检定你+2技能值。
      强制 - 若马克·哈里根身上有5点或更多伤害：翻面。
背面：索菲不能离场。你每项技能-1。
      强制 - 若马克·哈里根身上有4点或更少伤害：翻面。

简化说明：
- [fast] 能力实现为 spend()（可多次支付叠加，与 ResourceSkillBoost 同一惯例），
  加值应用到下一次 SKILL_VALUE_DETERMINED，检定结束时清除。
- 翻面状态记录在实现实例上（_flipped）；翻面检查挂 DAMAGE_ASSIGNED 与 spend()
  内的直接伤害；治疗不经过事件总线，回翻需会话层在治疗后调用 check_flip()。
- "索菲不能离场"没有通用的离场拦截钩子（CARD_LEAVES_PLAY 不可取消），
  需要引擎支持，见卡内 docstring 与报告。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Sophie(CardImplementation):
    card_id = "sophie_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = 0      # 已支付伤害的 +2 次数（可叠加）
        self._flipped = False  # 背面（In Loving Memory）

    def spend(self, game_state, investigator_id: str) -> bool:
        """[fast]受到1点直接伤害：本次技能检定+2技能值（可叠加）。背面不可用。"""
        if self._flipped:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inv.damage += 1  # 直接伤害（不分配）
        self._armed += 1
        game_state.log_effect("💔 索菲：受到1点直接伤害，本次检定+2技能值")
        self.check_flip(game_state, investigator_id)
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        if self._flipped:
            # 背面：你每项技能-1
            ctx.modify_amount(-1, "sophie_flipped_penalty")
        elif self._armed:
            ctx.modify_amount(2 * self._armed, "sophie_boost")
            self._armed = 0

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = 0

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def check_flip_on_damage(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.investigator_id != inst.owner_id:
            return
        self.check_flip(ctx.game_state, ctx.investigator_id)

    def check_flip(self, game_state, investigator_id: str) -> bool:
        """强制翻面检查：≥5伤害翻背面，≤4伤害翻回正面。返回当前是否背面。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return self._flipped
        if not self._flipped and inv.damage >= 5:
            self._flipped = True
            self._armed = 0
            game_state.log_effect("💔 索菲：马克伤害达到5点，索菲翻面")
        elif self._flipped and inv.damage <= 4:
            self._flipped = False
            game_state.log_effect("💔 索菲：马克伤害降至4点或更少，索菲翻回正面")
        return self._flipped
