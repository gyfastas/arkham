"""The Red Clock (Level 2) — Rogue Asset. (08053)
卓越。使用(0充能)。
强制 - 在你的回合开始后：在此放置1充能，或取走此处所有充能作为资源。
然后，如果其正好有……
- 1充能：下次技能检定你+3技能值。
- 2充能：你可以移动最多2次。
- 3充能：这回合你可以进行一次额外行动。

简化说明：
- 强制二选一自动决策：充能<3时放置1充能，充能≥3时取走全部作为资源
  （攒到3充能拿额外行动、随后一轮取3资源的循环是常见打法；官方为玩家
  选择）。lv5 子类覆盖参数。
- "正好2充能：移动最多2次"为免费移动，引擎无回合内免费移动通道
  （引擎缺口）：仅记录 ctx.extra["red_clock_free_moves"] 与日志，
  由会话层消费。
- "下次技能检定+N"武装后在最近一次检定的 SKILL_VALUE_DETERMINED 生效
  并消耗（不限回合，与官方一致）。
- "卓越"为牌组构建规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheRedClockLv2(CardImplementation):
    card_id = "the_red_clock_lv2"
    skill_bonus = 3        # 正好1充能：下次检定+N
    free_moves = 2         # 正好2充能：免费移动次数
    bonus_actions = 1      # 正好3充能：额外行动数
    take_threshold = 3     # 充能达到该值时自动取走作为资源
    always_place = False   # lv5：取走后仍放置1充能

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._next_test_bonus = 0

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.FORCED)
    def resolve_clock(self, ctx):
        """强制 - 你的回合开始后：放置/取走充能，并按正好充能数结算效果。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return

        charges = inst.uses.get("charges", 0)
        if charges >= self.take_threshold:
            inv.resources += charges
            inst.uses["charges"] = 0
            ctx.extra["red_clock_took_resources"] = charges
            ctx.game_state.log_effect(f"⏰ 红色时钟：取走{charges}充能作为资源")
            charges = 0
        if not self.always_place and ctx.extra.get("red_clock_took_resources"):
            pass  # lv2：取走与放置二选一，取走则不再放置
        else:
            charges += 1
            inst.uses["charges"] = charges

        if charges == 1:
            self._next_test_bonus = self.skill_bonus
            ctx.extra["red_clock_skill_bonus"] = self.skill_bonus
            ctx.game_state.log_effect(
                f"⏰ 红色时钟：正好1充能，下次技能检定+{self.skill_bonus}")
        elif charges == 2:
            ctx.extra["red_clock_free_moves"] = self.free_moves
            ctx.game_state.log_effect(
                f"⏰ 红色时钟：正好2充能，可移动最多{self.free_moves}次")
        elif charges == 3:
            inv.actions_remaining += self.bonus_actions
            ctx.extra["red_clock_bonus_actions"] = self.bonus_actions
            ctx.game_state.log_effect(
                f"⏰ 红色时钟：正好3充能，本回合+{self.bonus_actions}行动")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_next_test_bonus(self, ctx):
        """正好1充能的效果：下一次技能检定+N（不限技能）。"""
        if not self._next_test_bonus:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(self._next_test_bonus, "red_clock_next_test")
        ctx.extra["red_clock_applied"] = self._next_test_bonus
        self._next_test_bonus = 0
