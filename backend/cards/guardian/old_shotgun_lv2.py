"""Old Shotgun (Level 2) — Guardian Asset, Hand x2. (08088)
使用(0弹药)。当你打出事件时，视旧霰弹枪的使用值为2。
[行动]花费1弹药：攻击。本次攻击你获得+3战斗。本次攻击不造成标准伤害，
改为造成等同于你成功超出点数的伤害，或你失败且将误伤另一位调查员时
等同于失败点数的伤害（最少1点，最多3点）。

简化说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本卡发起攻击）时扣除（未命中同样消耗，
  同 rolands_38_special）；0弹药时仍可发起攻击但无任何加值（同该约定，
  武器可选项由会话层过滤）。
- 成功伤害 = 成功超出点数（下限1上限3），经 bonus_damage = damage-1 使
  总伤害=damage（其他+伤害效果在其上叠加，同 shotgun_lv4）。
- 失败误伤分支：引擎未实现误伤调查员流程（天然无效果，注明）。
- "打出事件时使用值视为2"：引擎没有读取使用值的事件通道（如弃牌换资源
  类事件未实现），暂不生效（引擎缺口，注明）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_MIN_DAMAGE = 1
_MAX_DAMAGE = 3


class OldShotgun(CardImplementation):
    card_id = "old_shotgun_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_on_attack(self, ctx):
        """花费1弹药作为攻击费用。"""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+3 战斗（需已付弹药）。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(3, "old_shotgun_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def variable_damage(self, ctx):
        """伤害 = 成功超出点数（下限1上限3），替代标准伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        succeed_by = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        damage = min(max(succeed_by, _MIN_DAMAGE), _MAX_DAMAGE)
        # bonus_damage 在标准伤害(1)之上追加；+damage-1 使总伤害=damage
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) \
            + damage - 1
        ctx.extra["old_shotgun_damage"] = damage

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._attack_paid = False
