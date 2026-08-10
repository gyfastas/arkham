"""Twilight Blade (Level 0) — Neutral Asset, Hand slot. 戴安娜·斯坦利专属。
[行动]：战斗。本次攻击你可以使用意志代替战斗。
你可以打出或投入戴安娜·斯坦利下方的事件和技能卡，如同其在你的手牌中。
以此法打出或投入卡牌时，横置银暮匕首作为额外费用。以此法打出或投入
卡牌时，你不能触发戴安娜·斯坦利的[反应]能力。

简化说明：
- 战斗部分：activate(use_willpower=True) 武装后由会话层发起战斗行动
  （weapon_instance_id 传本卡实例）；意志代替战斗经 SKILL_VALUE_DETERMINED
  换技实现（同 shrivelling_lv0）。use_willpower=False 即普通战斗。
- "戴安娜下方的卡牌"没有引擎级存储/打出通道：按 stars_of_hyades_lv0 惯例
  以 scenario.vars["beneath_{investigator_id}"] 表达卡 id 列表；
  playable_beneath() 返回可经本能力打出/投入的卡（事件/技能且匕首就绪），
  实际打出/投入与戴安娜反应抑制需引擎/会话层接线（引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class TwilightBlade(CardImplementation):
    card_id = "twilight_blade_lv0"
    activations = [{
        "id": "fight",
        "label": "[行动]战斗（可用意志代替战斗）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._use_willpower = True

    def activate(self, game_state, investigator_id: str,
                 use_willpower: bool = True) -> bool:
        """[行动]武装一次攻击；use_willpower 选择是否以意志代替战斗。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        self._armed = True
        self._use_willpower = bool(use_willpower)
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        """本次攻击可使用意志代替战斗。"""
        if ctx.skill_type != Skill.COMBAT or not self._armed:
            return
        if ctx.source != self.instance_id or not self._use_willpower:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, "twilight_blade_substitute")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False

    def playable_beneath(self, game_state, investigator_id) -> list[str]:
        """戴安娜下方可经本能力打出/投入的事件与技能卡 id 列表。

        额外费用为横置本卡（匕首已横置时不可用）；以此法打出/投入时不能
        触发戴安娜的[反应]能力（会话层在走该通道时抑制）。
        """
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return []
        if self.instance_id not in inv.play_area or inst.exhausted:
            return []
        beneath = game_state.scenario.vars.get(
            f"beneath_{investigator_id}", []) or []
        out = []
        for card_id in beneath:
            cd = game_state.get_card_data(card_id)
            if cd is not None and cd.type in (CardType.EVENT, CardType.SKILL):
                out.append(card_id)
        return out
