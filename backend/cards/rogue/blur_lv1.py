"""Blur (Level 1) — Rogue Asset, Arcane slot. (08109)
使用(3充能)。
[行动]如果身形虚化还有剩余充能：躲避。这次躲避尝试你可以不使用敏捷，
改为使用意志，并且你+1技能值。如果你成功，花费1充能并且这回合你可以
进行一个额外行动。如果你成功且等于难度，受到1点伤害。

简化说明：
- activate() 武装一次躲避（不消耗本卡——卡面无横置要求）；随后由会话层
  发起躲避行动（suggestion 同模式；武装在 SKILL_TEST_ENDS 清除）。
- "可以使用意志代替敏捷"简化为自动取两者中较高者（有利且确定）。
- 成功时自动花费1充能并获得1个额外行动（充能不足则无行动）。
- "成功且等于难度受1点伤害"直接加在调查员上（不经伤害分配窗口，
  shrivelling 恐惧同例）。
- 数据笔误兼容：JSON 的 uses 键为 "chargess"，首次访问时规整为 "charges"
  （segment_of_onyx 同例）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BlurLv1(CardImplementation):
    card_id = "blur_lv1"
    skill_bonus = 1          # lv4 覆盖为 2
    max_extra_actions = 1    # lv4 覆盖为 2
    zero_margin_damage = 1   # lv4 覆盖为 2

    activations = [{
        "id": "evade",
        "label": "躲避（可用意志代替敏捷；成功花充能得额外行动）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False

    @staticmethod
    def _normalize_uses(inst) -> None:
        if inst is not None and "chargess" in inst.uses:  # 数据笔误兼容
            value = inst.uses.pop("chargess")
            inst.uses.setdefault("charges", value)

    def activate(self, game_state, investigator_id: str) -> bool:
        """武装一次躲避（要求本卡还有剩余充能）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        self._normalize_uses(inst)
        if inst is None or inst.uses.get("charges", 0) < 1:
            return False
        self._armed = True
        return True

    def _is_armed_evade(self, ctx) -> bool:
        return self._armed and ctx.skill_type == Skill.AGILITY

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_and_bonus(self, ctx):
        """可用意志代替敏捷（自动取高者），并+1技能值。"""
        if not self._is_armed_evade(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            base = inv.get_skill(Skill.AGILITY)
        willpower = inv.get_skill(Skill.WILLPOWER)
        if willpower > base:
            ctx.modify_amount(willpower - base, "blur_substitute_willpower")
        ctx.modify_amount(self.skill_bonus, "blur_skill_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def spend_charge_for_actions(self, ctx):
        """成功：花费充能并获得等量额外行动；恰等于难度则受伤。"""
        if not self._is_armed_evade(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        self._normalize_uses(inst)
        if inst is not None:
            spend = min(self.max_extra_actions, inst.uses.get("charges", 0))
            if spend > 0:
                inst.uses["charges"] -= spend
                inv.actions_remaining += spend
                ctx.extra["blur_extra_actions"] = spend
                ctx.game_state.log_effect(
                    f"💨 身形虚化：花费{spend}充能，本回合额外{spend}个行动")
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin == 0:
            inv.damage += self.zero_margin_damage
            ctx.extra["blur_zero_margin_damage"] = self.zero_margin_damage
            ctx.game_state.log_effect(
                f"💨 身形虚化：恰好成功，受到{self.zero_margin_damage}点伤害")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
