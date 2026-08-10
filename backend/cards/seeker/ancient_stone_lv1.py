"""Ancient Stone (Level 1) — Seeker Asset, Hand slot. (04022)
[行动]：调查。本次调查中你所在地点+3隐蔽值。如果你成功，在你所在地点额外
发现1条线索，丢弃远古之石，并在冒险日志中记录"你已查明远古之石"，并在其
后的括号中记录本次技能检定的难度。

简化说明：
- activate() 武装一次调查（官方为[行动]能力；随后由会话层发起调查行动，
  与 flashlight / rite_of_seeking 同款武装模式）；
- 难度修正（+3隐蔽）在 SKILL_TEST_BEGINS 施加；额外线索在基础发现的
  CLUE_DISCOVERED 之后补发（与 deduction 同序）；
- 成功但地点已无线索（无基础发现）时仍丢弃并记录冒险日志（官方"If you
  succeed"不要求实际发现线索）；
- 冒险日志记录在 scenario.vars["campaign_log"]，括号中的难度另存
  scenario.vars["identified_stone_difficulty"]（供远古之石(4)读取）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority

CAMPAIGN_LOG_ENTRY = "你已查明远古之石"
DIFFICULTY_VAR = "identified_stone_difficulty"


class AncientStoneLv1(CardImplementation):
    card_id = "ancient_stone_lv1"
    activations = [{
        "id": "investigate",
        "label": "[行动]调查：地点+3隐蔽；成功额外发现1线索并查明石头",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_by: str | None = None
        self._succeeded = False
        self._difficulty: int | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]：武装一次"+3隐蔽的调查"。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed_by = investigator_id
        self._succeeded = False
        self._difficulty = None
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def raise_shroud(self, ctx):
        """本次调查：地点+3隐蔽（难度+3）。"""
        if self._armed_by != ctx.investigator_id:
            return
        if ctx.skill_type != Skill.INTELLECT or ctx.difficulty is None:
            return
        ctx.difficulty += 3
        ctx.extra["ancient_stone_raised"] = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def mark_success(self, ctx):
        if self._armed_by != ctx.investigator_id:
            return
        self._succeeded = True
        self._difficulty = ctx.difficulty

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.AFTER)
    def extra_clue(self, ctx):
        """成功：基础发现之后，在所在地点额外发现1条线索。"""
        if not self._succeeded or self._armed_by != ctx.investigator_id:
            return
        if ctx.extra.get("ancient_stone_extra_clue"):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        loc = ctx.game_state.get_location(ctx.location_id or inv.location_id) \
            if inv else None
        if inv is not None and loc is not None and loc.clues > 0:
            loc.clues -= 1
            inv.clues += 1
            ctx.extra["ancient_stone_extra_clue"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_and_clear(self, ctx):
        """成功结算：丢弃远古之石并记录冒险日志（含括号难度）。"""
        armed_by, self._armed_by = self._armed_by, None
        succeeded, self._succeeded = self._succeeded, False
        difficulty, self._difficulty = self._difficulty, None
        if armed_by != ctx.investigator_id or not succeeded:
            return
        inv = ctx.game_state.get_investigator(armed_by)
        if inv is None:
            return
        if self.instance_id in inv.play_area:
            vacate_asset_slots(ctx.game_state, self.instance_id)
            inv.play_area.remove(self.instance_id)
            ctx.game_state.cards_in_play.pop(self.instance_id, None)
            inv.discard.append(self.card_id)
        log = ctx.game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY not in log:
            log.append(CAMPAIGN_LOG_ENTRY)
        if difficulty is not None:
            ctx.game_state.scenario.vars[DIFFICULTY_VAR] = difficulty
        ctx.game_state.log_effect(
            f"🪨 远古之石：调查成功（难度{difficulty}），额外发现1线索，"
            "丢弃本卡并记录冒险日志"
        )
