"""Spirit Athame (Level 1) — Mystic Asset, Hand slot. (03035)
[fast] 进行[[法术]]卡上的技能检定时，横置灵力祭祀刀：本次检定你+2技能值。
[action] 横置灵力祭祀刀：<b>攻击</b>。本次攻击你+2[combat]。

简化说明：
- 两个能力都要横置，同一回合只能用其中一个（就绪状态自然限制）。
- 法术检定加值：activate_spell_boost() 横置并武装；通过检定来源卡
  （ctx.source）的 spell 特性判定"法术卡上的检定"。无来源的法术事件检定
  识别不到——引擎缺口：检定上下文缺少发起卡 id。
- 攻击：activate_fight() 横置并武装；随后由会话层发起战斗行动
  （weapon_instance_id 传本卡实例），与 shrivelling 同模式。官方卡面攻击
  无充能消耗，造成标准1点伤害。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SpiritAthame(CardImplementation):
    card_id = "spirit_athame_lv1"
    activations = [
        {
            "id": "spell_boost",
            "label": "【快速】横置：法术卡检定+2技能值",
            "method": "activate_spell_boost",
        },
        {
            "id": "fight",
            "label": "横置：攻击，本次攻击+2战斗",
            "method": "activate_fight",
            "actions": 1,
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._fight_armed = False
        self._boost_armed = False

    def _exhaust(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        return True

    def activate_spell_boost(self, game_state, investigator_id: str) -> bool:
        """【快速】横置：本次法术卡技能检定+2技能值。"""
        if not self._exhaust(game_state, investigator_id):
            return False
        self._boost_armed = True
        return True

    def activate_fight(self, game_state, investigator_id: str) -> bool:
        """横置：武装一次+2战斗的攻击。"""
        if not self._exhaust(game_state, investigator_id):
            return False
        self._fight_armed = True
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_bonuses(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        # 攻击加值：仅当本次检定是以本卡发起的攻击
        if self._fight_armed and ctx.source == self.instance_id \
                and ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "spirit_athame_fight")
            return
        # 法术检定加值：来源卡带 spell 特性
        if self._boost_armed and self._is_spell_test(ctx):
            ctx.modify_amount(2, "spirit_athame_spell_boost")
            self._boost_armed = False

    def _is_spell_test(self, ctx) -> bool:
        if ctx.source is None:
            return False
        ci = ctx.game_state.get_card_instance(ctx.source)
        if ci is None:
            return False
        cd = ctx.game_state.get_card_data(ci.card_id)
        return cd is not None and "spell" in (cd.traits or [])

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._fight_armed = False
        self._boost_armed = False
