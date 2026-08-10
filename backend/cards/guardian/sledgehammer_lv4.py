"""Sledgehammer (Level 4) — Guardian Asset, Hand x2 slot. (08096)
[action]：<b>攻击</b>。你这次攻击+1[combat]并造成+1伤害。
[action][action][action]：<b>攻击</b>。你这次攻击+5[combat]并造成+5伤害。

简化说明：同 sledgehammer_lv0（数值与重击行动费用不同）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MODES = {
    "light": (1, 1),   # (战斗修正, 加伤)
    "heavy": (5, 5),
}


class SledgehammerLv4(CardImplementation):
    card_id = "sledgehammer_lv4"
    activations = [
        {
            "id": "fight_light",
            "label": "攻击：+1战斗，+1伤害",
            "method": "activate_light",
            "actions": 1,
            "target": "enemy",
        },
        {
            "id": "fight_heavy",
            "label": "攻击(3行动)：+5战斗，+5伤害",
            "method": "activate_heavy",
            "actions": 3,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._mode: str | None = None

    def activate_light(self, game_state, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        """[action] 武装轻击：+1战斗/+1伤害。"""
        return self._arm(game_state, investigator_id, "light")

    def activate_heavy(self, game_state, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        """[action][action][action] 武装重击：+5战斗/+5伤害。"""
        return self._arm(game_state, investigator_id, "heavy")

    def _arm(self, game_state, investigator_id: str, mode: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._mode = mode
        return True

    def _is_this_attack(self, ctx) -> bool:
        return (
            self._mode is not None
            and ctx.skill_type == Skill.COMBAT
            and ctx.source == self.instance_id
        )

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_modifier(self, ctx):
        if not self._is_this_attack(ctx):
            return
        combat_mod, _ = _MODES[self._mode]
        ctx.modify_amount(combat_mod, f"sledgehammer_lv4_{self._mode}")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if not self._is_this_attack(ctx):
            return
        _, damage = _MODES[self._mode]
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + damage

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._mode = None
