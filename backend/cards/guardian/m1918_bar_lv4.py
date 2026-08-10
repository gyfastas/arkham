"""M1918 BAR (Level 4) — Guardian Asset, Hand x2. (04229)
使用(8弹药)。
[行动]花费1-5弹药：攻击。本次攻击你获得+X战斗。本次攻击不造成标准伤害，
改为造成X点伤害。X为本能力费用中花费的弹药数。

简化说明：
- 弹药花费经公开方法 activate_fight(x=...)（会话层调用后发起 FIGHT 行动，
  weapon_instance_id 传本卡实例）；X 需在1-5且弹药足够，否则失败不武装。
- +X战斗在 SKILL_VALUE_DETERMINED 结算；伤害替换经 bonus_damage += X-1
  使总伤害=X（其他+伤害效果在此基础上叠加，与 shotgun 同一约定）。
- 攻击结束后（无论成败）清除武装；弹药已在启动时花费。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class M1918Bar(CardImplementation):
    card_id = "m1918_bar_lv4"
    activations = [{
        "id": "fight",
        "label": "[行动] 花1-5弹药：攻击，+X战斗/造成X伤害",
        "method": "activate_fight",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._x = 0

    def activate_fight(self, game_state, investigator_id: str, x: int = 1) -> bool:
        """[行动] 花费X(1-5)弹药：武装一次 +X战斗/X伤害 的攻击。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        x = int(x)
        if x < 1 or x > 5:
            return False
        if inst.uses.get("ammo", 0) < x:
            return False
        inst.uses["ammo"] -= x
        self._x = x
        game_state.log_effect(
            f"🔫 M1918 BAR：花费{x}弹药，本次攻击+{x}战斗/造成{x}伤害")
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._x > 0 and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+X 战斗。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(self._x, "m1918_bar_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def variable_damage(self, ctx):
        """伤害替换为X（bonus_damage = X-1，其他+伤害在其上叠加）。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) \
            + self._x - 1
        ctx.extra["m1918_bar_damage"] = self._x

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._x = 0
