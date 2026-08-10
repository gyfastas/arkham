"""Tristan Botley (Level 2) — Rogue Asset, Ally. (07194)
[reaction] 在你的回合开始后：选择两项技能。这些技能你每项得到+1，直到你的
下回合开始。
[reaction] 在任何抽出总计至少3个[curse]或[bless]标记的技能检定结束后：从你
手牌免费打出崔斯丹‧波特雷。

简化说明：
- "选择两项技能"自动选择你基础值最高的两项（平局按意志>智力>战斗>敏捷；
  官方为玩家选择）。
- 祝福/诅咒计数：引擎单标记揭示流程每次检定只揭示1个标记，3+标记实际
  只会出现在多次揭示（标记效果再抽等）场景；计数在每次检定开始清零。
- 从手牌免费打出：引擎只为在场/投入的卡激活实现（手牌中的实现不监听
  事件——引擎缺口）；本处理在实现已激活时（如测试直接注册）可用。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority

_SKILLS = (Skill.WILLPOWER, Skill.INTELLECT, Skill.COMBAT, Skill.AGILITY)


class TristanBotley(CardImplementation):
    card_id = "tristan_botley_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chosen: tuple[Skill, Skill] | None = None
        self._tokens_this_test = 0

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus  # 免费入场需要注册新实现实例并发 CARD_ENTERS_PLAY

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.REACTION)
    def choose_two_skills(self, ctx):
        """你的回合开始后：选两项技能（自动选基础值最高的两项），各+1直到下回合开始。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ranked = sorted(_SKILLS, key=lambda s: -inv.get_skill(s))
        self._chosen = (ranked[0], ranked[1])
        ctx.extra["tristan_chosen"] = [s.value for s in self._chosen]
        ctx.game_state.log_effect(
            f"🎩 崔斯丹·波特雷：{self._chosen[0].value}/{self._chosen[1].value} +1直到下回合开始")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        if not self._chosen or ctx.skill_type not in self._chosen:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(1, "tristan_botley_boost")

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.AFTER)
    def reset_token_count(self, ctx):
        self._tokens_this_test = 0

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.AFTER)
    def count_bless_curse(self, ctx):
        if ctx.chaos_token in (ChaosTokenType.BLESS, ChaosTokenType.CURSE):
            self._tokens_this_test += 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.REACTION)
    def play_from_hand_free(self, ctx):
        """检定中抽出3+祝福/诅咒标记后：从手牌免费打出。"""
        if self._tokens_this_test < 3:
            return
        holder = None
        for inv in ctx.game_state.investigators.values():
            if self.card_id in inv.hand:
                holder = inv
                break
        if holder is None or self._bus is None:
            return
        holder.hand.remove(self.card_id)
        from backend.models.state import CardInstance
        new_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=new_id,
            card_id=self.card_id,
            owner_id=holder.investigator_id,
            controller_id=holder.investigator_id,
        )
        cd = ctx.game_state.get_card_data(self.card_id)
        if cd is not None and cd.uses:
            ci.uses = dict(cd.uses)
        ctx.game_state.cards_in_play[new_id] = ci
        holder.play_area.append(new_id)
        # 为在场实例注册新的实现（本实例仍绑定原 instance_id）
        self.__class__(new_id).register(self._bus, new_id)
        from backend.engine.event_bus import EventContext
        self._bus.emit(EventContext(
            game_state=ctx.game_state,
            event=GameEvent.CARD_ENTERS_PLAY,
            investigator_id=holder.investigator_id,
            target=new_id,
            extra={"card_id": self.card_id},
        ))
        ctx.extra["tristan_played_free"] = new_id
        ctx.game_state.log_effect("🎩 崔斯丹·波特雷：检定抽出3+祝福/诅咒，从手牌免费入场")
