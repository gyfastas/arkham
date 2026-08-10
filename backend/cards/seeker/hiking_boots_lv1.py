"""Hiking Boots (Level 1) — Seeker Asset. (08035)
每位调查员限制1[[鞋子]]。你获得+1敏捷。
[反应]在你所在地点的最后1个线索被发现后，消耗登山靴：移动到有至少1个
线索的连接地点，或未揭示的连接地点。

简化说明：
- "+1敏捷"为常驻加值（SKILL_VALUE_DETERMINED，与 dr_milan 一致）；
- 反应自动触发（官方为玩家可选）：优先移动到第一个有线索的连接地点，
  否则第一个未揭示连接地点；两者皆无则不消耗不移动；
- 目的地可用公开方法 activate(destination=...) 显式指定（供会话层/测试）；
- "限1鞋子"的槽位约束由会话层/组牌负责（引擎无 Footwear 子槽，引擎缺口）；
- 移动不携带交战敌人（引擎 _move 同款简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class HikingBoots(CardImplementation):
    card_id = "hiking_boots_lv1"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def agility_bonus(self, ctx):
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "hiking_boots_agility")

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.REACTION)
    def move_after_last_clue(self, ctx):
        """你所在地点最后1个线索被发现后：消耗本卡，自动移动。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if ctx.location_id != inv.location_id:
            return
        location = ctx.game_state.get_location(ctx.location_id)
        if location is None or location.clues > 0:
            return
        if self.activate(ctx.game_state, ctx.investigator_id):
            ctx.extra["hiking_boots_moved"] = inv.location_id

    def activate(self, game_state, investigator_id: str,
                 destination: str | None = None) -> bool:
        """消耗登山靴：移动到有线索或未揭示的连接地点。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        here = game_state.get_location(inv.location_id)
        if here is None:
            return False

        clued, unrevealed = [], []
        for cid in (here.connections or []):
            loc = game_state.get_location(cid)
            if loc is None:
                continue
            if loc.clues > 0:
                clued.append(cid)
            if not loc.revealed:
                unrevealed.append(cid)
        if destination is not None:
            if destination not in clued and destination not in unrevealed:
                return False
            target = destination
        elif clued:
            target = clued[0]
        elif unrevealed:
            target = unrevealed[0]
        else:
            return False

        inst.exhausted = True
        inv.location_id = target
        game_state.log_effect(f"🥾 登山靴：消耗，移动到连接地点【{target}】")
        return True
