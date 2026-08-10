"""The Black Fan (Level 3) — Rogue Asset. (08057)
卓越。
只要你有……
- ……10+资源，你获得+1生命和+1神智。
- ……15+资源，在你回合中你可以进行一次额外行动。
- ……20+资源，你的每项技能+1。

简化说明：
- +1生命/+1神智经 health_bonus/sanity_bonus 差量维护（RESOURCES_GAINED/
  RESOURCES_SPENT/入场时重算），不覆盖其他卡的同类加值。
- 15+资源的额外行动在你回合开始（INVESTIGATOR_TURN_BEGINS）按当前资源
  判定发放；回合内才达到15资源不补发（引擎无"回合内获得行动"窗口，简化）。
- 20+资源：每次技能检定 SKILL_VALUE_DETERMINED +1。
- "卓越"（购买2张同名卡）为牌组构建规则，引擎无校验通道（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_SOAK_THRESHOLD = 10
_ACTION_THRESHOLD = 15
_SKILL_THRESHOLD = 20


class TheBlackFan(CardImplementation):
    card_id = "the_black_fan_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._soak_contrib = 0  # 本卡当前贡献的 health/sanity bonus（0 或 1）

    def _owner(self, ctx, investigator_id=None):
        inv = ctx.game_state.get_investigator(investigator_id or ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        return inv

    def _update_soak(self, inv) -> None:
        """10+资源：+1生命/+1神智（按差量调整，不覆盖其他来源）。"""
        target = 1 if inv.resources >= _SOAK_THRESHOLD else 0
        delta = target - self._soak_contrib
        if delta:
            inv.health_bonus += delta
            inv.sanity_bonus += delta
            self._soak_contrib = target

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def apply_on_enter(self, ctx):
        if ctx.target != self.instance_id:
            return
        inv = self._owner(ctx)
        if inv is not None:
            self._update_soak(inv)

    @on_event(GameEvent.RESOURCES_GAINED, priority=TimingPriority.AFTER)
    @on_event(GameEvent.RESOURCES_SPENT, priority=TimingPriority.AFTER)
    def update_on_resource_change(self, ctx):
        inv = self._owner(ctx)
        if inv is not None:
            self._update_soak(inv)

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.WHEN)
    def grant_action(self, ctx):
        """15+资源：回合中+1行动。"""
        inv = self._owner(ctx)
        if inv is None or inv.resources < _ACTION_THRESHOLD:
            return
        inv.actions_remaining += 1
        ctx.extra["black_fan_extra_action"] = True
        ctx.game_state.log_effect("🪭 黑扇：资源15+，本回合+1行动")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """20+资源：每项技能+1。"""
        inv = self._owner(ctx)
        if inv is None or inv.resources < _SKILL_THRESHOLD:
            return
        ctx.modify_amount(1, "black_fan_skill_bonus")
