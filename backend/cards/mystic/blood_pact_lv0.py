"""Blood Pact (Level 0) — Mystic Asset. (07158)
[fast]在鲜血盟约上增加1个毁灭标记：本次技能检定你+2[willpower]。（每次检定限一次。）
[fast]在鲜血盟约上增加1个毁灭标记：本次技能检定你+2[combat]。（每次检定限一次。）

简化说明：
- 两个快速能力共用 boost()（skill 参数区分）；会话层在检定中调用。
- 毁灭标记放在本卡实例上（计入场上总毁灭，引擎 total_doom_in_play 已覆盖）。
- 每个能力每次检定限一次：武装状态在 SKILL_TEST_ENDS 清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

BOOSTABLE = (Skill.WILLPOWER, Skill.COMBAT)


class BloodPact(CardImplementation):
    card_id = "blood_pact_lv0"
    activations = [
        {"id": "boost_willpower", "label": "[快速]加1毁灭：本次检定+2意志",
         "method": "boost_willpower"},
        {"id": "boost_combat", "label": "[快速]加1毁灭：本次检定+2战斗",
         "method": "boost_combat"},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed: set[Skill] = set()  # 本次检定已发动的能力

    def boost_willpower(self, game_state, investigator_id: str) -> bool:
        return self.boost(game_state, investigator_id, Skill.WILLPOWER)

    def boost_combat(self, game_state, investigator_id: str) -> bool:
        return self.boost(game_state, investigator_id, Skill.COMBAT)

    def boost(self, game_state, investigator_id: str, skill: Skill) -> bool:
        """[fast]在本卡上放置1毁灭：本次检定+2对应技能（每次检定限一次）。"""
        if skill not in BOOSTABLE or skill in self._armed:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        inst.doom += 1
        self._armed.add(skill)
        game_state.log_effect(f"🩸 鲜血盟约：+1毁灭，本次检定+2{skill.value}")
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        if ctx.skill_type not in self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(2, f"{self.card_id}_boost")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed.clear()
