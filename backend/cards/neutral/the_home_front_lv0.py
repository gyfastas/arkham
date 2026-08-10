"""The Home Front (Level 0) — Neutral Skill, Signature (Mark Harrigan).
4个战斗图标由 skill_icons 数据经提交流程自动结算。
如果攻击中的这次技能检定成功，将马克·哈里根身上的1点伤害移动到受到攻击的敌人身上。

实现说明：
- SKILL_TEST_SUCCESSFUL（战斗检定、投入了本卡）武装标志；随后攻击结算的
  DAMAGE_DEALT（_fight.on_success → deal_damage_to_enemy）中把马克的1点伤害
  转为本次攻击的+1伤害（净效果等同"移动1点伤害"）。
- 马克身上无伤害时不提供加伤；标志在检定结束时清除（非攻击检定不触发）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class TheHomeFront(CardImplementation):
    card_id = "the_home_front_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_for: str | None = None

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def arm_on_success(self, ctx):
        if "the_home_front_lv0" not in (ctx.committed_cards or []):
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        self._armed_for = ctx.investigator_id

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def move_damage(self, ctx):
        if self._armed_for is None or ctx.investigator_id != self._armed_for:
            return
        # 目标是敌人才算"攻击"
        target = ctx.game_state.get_card_instance(ctx.target) if ctx.target else None
        target_data = ctx.game_state.get_card_data(target.card_id) if target else None
        if target_data is None or target_data.type != CardType.ENEMY:
            return
        inv = ctx.game_state.get_investigator(self._armed_for)
        self._armed_for = None
        if inv is None or inv.damage < 1:
            return
        inv.damage -= 1
        ctx.modify_amount(1, "the_home_front_move_damage")
        ctx.game_state.log_effect("🏠 故乡前线：马克的1点伤害移动到被攻击的敌人")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_for = None
