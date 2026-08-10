"""Burglary (Level 2) — Rogue Asset. (06200)
[行动]消耗夜盗：调查。如果你成功，不发现线索，改为获得2资源，你每成功且
超过难度1点，额外获得+1资源（最大+3资源）。

简化说明（同 burglary_lv0 模式）：
- activate() 消耗本卡并武装；随后由会话层发起调查行动。
- 超出值在 SKILL_TEST_SUCCESSFUL 记录；CLUE_DISCOVERED 时返还线索并按
  2 + min(超出值, 3) 折算资源（事后校正）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BurglaryLv2(CardImplementation):
    card_id = "burglary_lv2"
    activations = [{
        "id": "investigate",
        "label": "消耗：调查，成功改为获得2资源（每超1点+1，至多+3）",
        "method": "activate",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        self._margin = 0

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        self._margin = 0
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def record_margin(self, ctx):
        """成功：记录超出值供资源折算。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        self._margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def resources_instead(self, ctx):
        """成功：不发现线索，改为获得 2 + min(超出值, 3) 资源（事后校正）。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if loc is not None:
            loc.clues += 1  # 返还线索
        inv.clues = max(0, inv.clues - 1)
        gained = 2 + min(3, max(0, self._margin))
        inv.resources += gained
        ctx.extra["burglary_lv2_resources"] = gained
        ctx.game_state.log_effect(
            f"🌙 夜盗(2级)：不发现线索，改为获得{gained}资源")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._margin = 0
