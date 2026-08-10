"""Mariner's Compass (Level 0) — Survivor Asset, Hand slot. (07121)
[action] Exhaust Mariner's Compass: Investigate. If you succeed and have
no resources in your resource pool, discover 1 additional clue at your
location.
[fast] During an investigation using Mariner's Compass, spend 1 resource:
You get +1 [intellect] for this skill test. (Limit three times per
investigation.)

简化说明：
- 调查能力沿用 Lantern 的"启动武装"模式：activate() 横置并武装，随后由
  会话层发起调查行动；仅对调查行动（INVESTIGATE_ACTION_INITIATED 跟踪）
  生效。
- 花费能力沿用 ResourceSkillBoost，每次调查限3次、仅罗盘武装的调查生效。
- 额外线索在成功且资源池为0时自动结算（地点线索不足时从简不补）。
"""

from backend.cards._shared import ResourceSkillBoost
from backend.cards.base import on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class MarinersCompass(ResourceSkillBoost):
    card_id = "mariners_compass_lv0"
    boosted_skills = (Skill.INTELLECT,)
    spend_limit_per_investigation = 3
    activations = [{
        "id": "investigate",
        "label": "横置罗盘：调查（资源为0时成功多发现1线索）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._compass_armed: str | None = None   # 已武装调查的调查员
        self._investigating: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[action] 横置罗盘：调查（武装后由会话层发起调查行动）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._compass_armed = investigator_id
        return True

    def spend(self, game_state, investigator_id: str, skill: Skill) -> bool:
        """[fast] 花1资源：本次罗盘调查 +1 智力（每次调查限3次）。"""
        if self._compass_armed != investigator_id:
            return False
        if sum(self._armed.values()) >= self.spend_limit_per_investigation:
            return False
        return super().spend(game_state, investigator_id, skill)

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        """仅罗盘武装的调查生效，每次支付 +1 智力。"""
        count = self._armed.get(ctx.skill_type, 0)
        if not count:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._compass_armed != ctx.investigator_id:
            return
        if self._investigating != ctx.investigator_id:
            return
        ctx.modify_amount(count, "mariners_compass_boost")
        self._armed.pop(ctx.skill_type, None)

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_clue(self, ctx):
        """罗盘调查成功且资源池为0：额外发现1条线索。"""
        if ctx.skill_type != Skill.INTELLECT:
            return
        if self._compass_armed != ctx.investigator_id:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or inv.resources != 0:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None or loc.clues <= 0:
            return
        loc.clues -= 1
        inv.clues += 1
        ctx.extra["mariners_compass_clue"] = True
        ctx.game_state.log_effect(
            "🧭 水手罗盘：资源耗尽，额外发现1条线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        super().clear(ctx)
        self._compass_armed = None
        self._investigating = None
