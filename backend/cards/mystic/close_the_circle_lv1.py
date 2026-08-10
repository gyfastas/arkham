"""Close the Circle (Level 1) — Mystic Asset, Arcane slot. (08062)
使用（充能数等于你控制卡牌之中不同的职阶数，包含本卡牌）。
[fast]花费1充能并消耗闭环：进行一次基础行动。该行动期间执行的每次技能检定，
你可以不使用该行动指定的技能，改为使用你的[willpower]。

简化说明：
- 充能数在入场（CARD_ENTERS_PLAY）时按你控制的在场卡牌的职阶去重计算
  （含本卡自身）；此后不随场面变化重算。
- activate() 花费1充能并消耗，武装至下一个 ACTION_PERFORMED 结束
  （快速能力本身不经 perform_action，不会误清）。
- 意志代替为可选效果：自动取有利分支——仅当意志高于该检定技能基础值时替换。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class CloseTheCircle(CardImplementation):
    card_id = "close_the_circle_lv1"
    activations = [{
        "id": "take_action",
        "label": "[快速]花1充能+消耗：进行一次基础行动，检定可用意志代替",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def set_charges(self, ctx):
        """入场：充能数=你控制卡牌的不同职阶数（含本卡）。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        classes = set()
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            cd = ctx.game_state.get_card_data(ci.card_id) if ci else None
            if cd is not None:
                classes.add(cd.card_class)
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None:
            inst.uses["charges"] = len(classes)

    def activate(self, game_state, investigator_id: str) -> bool:
        """[fast]花费1充能并消耗：武装至下一个行动结束。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or inst.uses.get("charges", 0) <= 0:
            return False
        inst.uses["charges"] -= 1
        inst.exhausted = True
        self._armed_by = investigator_id
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """该行动期间的检定：可用意志代替指定技能（自动取有利分支）。"""
        if self._armed_by is None or ctx.investigator_id != self._armed_by:
            return
        if ctx.skill_type in (None, Skill.WILLPOWER):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        if willpower > base_val:
            ctx.modify_amount(willpower - base_val, "close_the_circle_substitute")
            ctx.extra["close_the_circle_substituted"] = ctx.skill_type.value

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_by = None
