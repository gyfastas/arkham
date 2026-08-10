"""Brand of Cthugha (Level 1) — Guardian Asset, Arcane slot. (08090)
使用(6充能)。[行动]：攻击。本次攻击你可以使用意志代替战斗，且获得+1技能值。
如果成功，花费1或2充能。本次攻击不造成标准伤害，改为每花费1充能造成1点伤害。
如果你成功超出0点，失去1个行动。

简化说明：
- activate() 武装一次攻击（官方行动由会话层发起，同 shrivelling）；
  "可以使用意志代替战斗"简化为自动选择：意志高于战斗时替换。
- 成功时花费充能简化为自动花费上限（2充能，不足则花光）；
  无充能时攻击造成标准伤害（无法启动替代伤害）。
- 数据 uses 键兼容 "charges"/"chargess"（抓取复数化瑕疵）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


def _uses_key(inst, base: str) -> str:
    """数据 uses 键存在复数化瑕疵（chargess/secretss/resourcess），运行时容错。"""
    if base in inst.uses:
        return base
    doubled = base + "s"
    return doubled if doubled in inst.uses else base


class BrandOfCthughaLv1(CardImplementation):
    card_id = "brand_of_cthugha_lv1"
    skill_bonus = 1        # lv4 覆盖：+2 技能值
    max_charges_spent = 2  # lv4 覆盖：至多花费3充能
    actions_lost_on_exact = 1  # lv4 覆盖：成功超出0点失去2行动
    activations = [{
        "id": "fight",
        "label": "攻击：可用意志代替战斗，+1技能值",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    def activate(self, game_state, investigator_id: str) -> bool:
        """武装一次克图格亚的烙印攻击。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_and_boost(self, ctx):
        """可用意志代替战斗（自动：意志更高时替换）；+1技能值。"""
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        if willpower > base_val:
            ctx.modify_amount(willpower - base_val, "brand_substitute")
        ctx.modify_amount(self.skill_bonus, "brand_skill_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def spend_charges_for_damage(self, ctx):
        """成功时：自动花费至多N充能，每充能1伤害（替代标准伤害）。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = _uses_key(inst, "charges")
        available = inst.uses.get(key, 0)
        spent = min(self.max_charges_spent, available)
        if spent <= 0:
            return  # 无充能：标准伤害
        inst.uses[key] -= spent
        # bonus_damage 通道在标准伤害(1)之上追加；spent-1 使总伤害=spent
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + spent - 1
        ctx.extra["brand_charges_spent"] = spent
        ctx.game_state.log_effect(f"🔥 克图格亚的烙印：花费{spent}充能，造成{spent}点伤害")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def lose_action_on_exact_success(self, ctx):
        """成功超出0点：失去行动。"""
        if not self._is_this_attack(ctx) or ctx.skill_type != Skill.COMBAT:
            return
        if (ctx.modified_skill or 0) == (ctx.difficulty or 0):
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and self.actions_lost_on_exact > 0:
                inv.actions_remaining = max(
                    0, inv.actions_remaining - self.actions_lost_on_exact)
                ctx.extra["brand_action_lost"] = self.actions_lost_on_exact
                ctx.game_state.log_effect(
                    f"🔥 克图格亚的烙印：成功超出0点，失去{self.actions_lost_on_exact}个行动")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
