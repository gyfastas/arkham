"""Sledgehammer (Level 0) — Guardian Asset, Hand x2 slot. (08094)
[action]：<b>攻击</b>。你这次攻击-1[combat]并造成+1伤害。
[action][action]：<b>攻击</b>。你这次攻击+2[combat]并造成+2伤害。

简化说明：
- 两种攻击模式为两个启动能力（动作费用由会话层按 activations 声明扣除）；
  activate_light()/activate_heavy() 武装后，由会话层以本卡实例为武器发起
  战斗行动（weapon_instance_id 传本卡实例）。
- 战斗修正仅对以本卡发起的攻击生效（ctx.source == 本卡实例），+伤害经
  ctx.extra["bonus_damage"] 通道汇入战斗结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MODES = {
    "light": (-1, 1),  # (战斗修正, 加伤)
    "heavy": (2, 2),
}


class Sledgehammer(CardImplementation):
    card_id = "sledgehammer_lv0"
    activations = [
        {
            "id": "fight_light",
            "label": "攻击：-1战斗，+1伤害",
            "method": "activate_light",
            "actions": 1,
            "target": "enemy",
        },
        {
            "id": "fight_heavy",
            "label": "攻击(2行动)：+2战斗，+2伤害",
            "method": "activate_heavy",
            "actions": 2,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._mode: str | None = None

    def activate_light(self, game_state, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        """[action] 武装轻击：-1战斗/+1伤害。"""
        return self._arm(game_state, investigator_id, "light")

    def activate_heavy(self, game_state, investigator_id: str,
                       enemy_instance_id: str | None = None) -> bool:
        """[action][action] 武装重击：+2战斗/+2伤害。"""
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
        ctx.modify_amount(combat_mod, f"sledgehammer_{self._mode}")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        if not self._is_this_attack(ctx):
            return
        _, damage = _MODES[self._mode]
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + damage

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._mode = None
