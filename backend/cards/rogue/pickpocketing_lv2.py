"""Pickpocketing (Level 2) — Rogue Asset.
快速。
[反应]在你躲避一名敌人后，消耗扒窃：抽取1张卡牌或获得1资源。
如果你成功且超出难度2点以上，改为执行以上两项。

简化说明：
- "抽1张牌或获得1资源"的选择需玩家输入；默认抽取1张卡牌
  （lv0 同行为），可用 set_choice() 预设为 "resource"
  （在下一次躲避反应时消费；成功超2时无视选择执行两项）。
- 超出难度在 SKILL_TEST_SUCCESSFUL（敏捷）捕获，躲避反应时读取。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class PickpocketingLv2(CardImplementation):
    card_id = "pickpocketing_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {investigator_id: 最近一次敏捷检定成功的超出点数}
        self._margins: dict[str, int] = {}
        # {investigator_id: "card" | "resource"} 玩家预设选择
        self._choices: dict[str, str] = {}

    def set_choice(self, game_state, investigator_id: str, choice: str) -> bool:
        """预设下一次躲避反应的选择："card"（默认）或 "resource"。"""
        if choice not in ("card", "resource"):
            return False
        self._choices[investigator_id] = choice
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def capture_margin(self, ctx):
        if ctx.skill_type != Skill.AGILITY:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        self._margins[ctx.investigator_id] = margin

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_margin(self, ctx):
        self._margins.pop(ctx.investigator_id, None)

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.REACTION)
    def react_on_evade(self, ctx):
        """躲避敌人后，消耗扒窃：抽1张牌或获得1资源；成功超2则两项。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        inst.exhausted = True

        margin = self._margins.get(ctx.investigator_id, 0)
        both = margin >= 2
        choice = self._choices.pop(ctx.investigator_id, "card")

        draw = both or choice == "card"
        gain = both or choice == "resource"
        if draw and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["pickpocketing_lv2_draw"] = True
        if gain:
            inv.resources += 1
            ctx.extra["pickpocketing_lv2_resource"] = True
