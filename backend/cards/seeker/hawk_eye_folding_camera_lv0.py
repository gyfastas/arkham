"""Hawk-Eye Folding Camera (Level 0) — Seeker Asset. (05154)
[反应]在你所在地点的最后1个线索被发现后：在本卡牌上放置1资源（从供应堆
拿取），作为证据。(每场游戏每个地点限制一次。)
只要本卡上有至少1/2/3个证据，你分别获得+1意志/+1智力/+1神智值。

简化说明：
- 反应自动触发（官方为玩家可选）：你所在地点线索归零的 CLUE_DISCOVERED
  结算后放置1个证据；
- "每场游戏每个地点限一次"按实例记录已触发地点（存 scenario.vars，
  跨离场/再入场保留）；
- 证据计数存 inst.uses["evidence"]；+1意志/+1智力经 SKILL_VALUE_DETERMINED
  常驻生效；+1神智值在证据达到3个时写入 inv.sanity_bonus，离场时经
  CARD_LEAVES_PLAY 回滚（部分离场路径在注销实现后才发该事件——此时
  加值残留，已列入引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_USED_VAR = "hawk_eye_camera_used_locations"


class HawkEyeFoldingCamera(CardImplementation):
    card_id = "hawk_eye_folding_camera_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._sanity_applied: str | None = None  # 已发放 +1 神智的调查员 id

    def _evidence(self, game_state) -> int:
        inst = game_state.get_card_instance(self.instance_id)
        return inst.uses.get("evidence", 0) if inst is not None else 0

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.REACTION)
    def place_evidence(self, ctx):
        """你所在地点的最后1个线索被发现后：放置1个证据。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if ctx.location_id != inv.location_id:
            return
        location = ctx.game_state.get_location(ctx.location_id)
        if location is None or location.clues > 0:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return

        used = ctx.game_state.scenario.vars.setdefault(_USED_VAR, {})
        locations = used.setdefault(self.instance_id, [])
        if ctx.location_id in locations:
            return
        locations.append(ctx.location_id)

        inst.uses["evidence"] = inst.uses.get("evidence", 0) + 1
        ctx.extra["hawk_eye_evidence"] = inst.uses["evidence"]
        ctx.game_state.log_effect(
            f"📷 鹰眼折叠相机：放置第{inst.uses['evidence']}个证据"
        )
        # 至少3个证据：+1 神智值
        if inst.uses["evidence"] >= 3 and self._sanity_applied is None:
            inv.sanity_bonus += 1
            self._sanity_applied = inv.investigator_id
            ctx.game_state.log_effect("📷 鹰眼折叠相机：证据≥3，你+1神智值")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonuses(self, ctx):
        """证据≥1：+1意志；证据≥2：+1智力。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        evidence = self._evidence(ctx.game_state)
        if evidence >= 1 and ctx.skill_type == Skill.WILLPOWER:
            ctx.modify_amount(1, "hawk_eye_willpower")
        elif evidence >= 2 and ctx.skill_type == Skill.INTELLECT:
            ctx.modify_amount(1, "hawk_eye_intellect")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def remove_sanity_bonus(self, ctx):
        """离场时回收 +1 神智（若仍在册）。"""
        if ctx.target != self.instance_id or self._sanity_applied is None:
            return
        inv = ctx.game_state.get_investigator(self._sanity_applied)
        self._sanity_applied = None
        if inv is not None:
            inv.sanity_bonus = max(0, inv.sanity_bonus - 1)
