"""杜克（Duke，Level 0）— "灰堆"皮特专属支援卡，盟友。
[行动]消耗杜克：攻击。该次攻击战斗基础值视为4，造成+1伤害。
[行动]消耗杜克：调查。该次调查智力基础值视为4；在使用该效果调查前，
你可以立刻移动到一个连接地点。

简化说明：
- 两个"启动杜克"能力实现为 activate_fight / activate_investigate 方法，
  由会话层/UI 在玩家选择启动时调用（消耗1行动并横置杜克）。
- "基础值视为4"通过 SKILL_VALUE_DETERMINED 修正实现：
  修正量 = 4 - 调查员当前基础技能值（投入图标与混沌标记修正仍保留）。
- "调查前移动"由调用方传入 destination 参数（必须是连接地点）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import Action, GameEvent, Skill, TimingPriority

DUKE_BASE_SKILL = 4


class Duke(CardImplementation):
    card_id = "duke_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 启动能力进行中时记录技能类型与调查员，用于基础值修正
        self._pending_skill: Skill | None = None
        self._pending_inv: str | None = None

    # ------------------------------------------------------------------
    # 启动能力（由会话层调用）
    # ------------------------------------------------------------------

    def activate_fight(self, game, investigator_id: str, enemy_instance_id: str) -> bool:
        """启动杜克攻击：横置杜克并消耗1行动，以基础战斗4攻击，命中+1伤害。"""
        duke = game.state.get_card_instance(self.instance_id)
        inv = game.state.get_investigator(investigator_id)
        enemy = game.state.get_card_instance(enemy_instance_id)
        if duke is None or inv is None or enemy is None:
            return False
        if duke.exhausted or inv.actions_remaining <= 0:
            return False

        duke.exhausted = True
        self._pending_skill = Skill.COMBAT
        self._pending_inv = investigator_id
        try:
            # 以杜克为"武器"发起攻击，使伤害来源指向杜克（用于+1伤害）
            game.action_resolver.perform_action(
                investigator_id, Action.FIGHT,
                enemy_instance_id=enemy_instance_id,
                weapon_instance_id=self.instance_id,
            )
        finally:
            self._pending_skill = None
            self._pending_inv = None
        return True

    def activate_investigate(
        self, game, investigator_id: str, destination: str | None = None
    ) -> bool:
        """启动杜克调查：横置杜克并消耗1行动，以基础智力4调查；
        若给出 destination（连接地点），先立刻移动到该地点。"""
        duke = game.state.get_card_instance(self.instance_id)
        inv = game.state.get_investigator(investigator_id)
        if duke is None or inv is None:
            return False
        if duke.exhausted or inv.actions_remaining <= 0:
            return False
        if destination is not None:
            current = game.state.get_location(inv.location_id)
            if current is None or destination not in current.connections:
                return False

        duke.exhausted = True
        if destination is not None:
            inv.location_id = destination

        self._pending_skill = Skill.INTELLECT
        self._pending_inv = investigator_id
        try:
            game.action_resolver.perform_action(
                investigator_id, Action.INVESTIGATE,
            )
        finally:
            self._pending_skill = None
            self._pending_inv = None
        return True

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    @on_event(
        GameEvent.SKILL_VALUE_DETERMINED,
        priority=TimingPriority.WHEN,
    )
    def base_skill_override(self, ctx):
        """启动杜克期间，对应技能的基础值视为4。"""
        if self._pending_skill is None or ctx.skill_type != self._pending_skill:
            return
        if ctx.investigator_id != self._pending_inv:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        diff = DUKE_BASE_SKILL - inv.get_skill(ctx.skill_type)
        if diff != 0:
            ctx.modify_amount(diff, "duke_base_skill_4")

    @on_event(
        GameEvent.DAMAGE_DEALT,
        priority=TimingPriority.WHEN,
    )
    def bonus_damage(self, ctx):
        """以杜克攻击时造成+1伤害。"""
        if ctx.source != self.instance_id:
            return
        ctx.modify_amount(1, "duke_bonus_damage")
