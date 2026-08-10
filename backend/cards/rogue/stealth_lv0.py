"""Stealth (Level 0) — Rogue Asset.
[行动]消耗潜行：躲避。本次躲避尝试所选敌人-2躲避。
如果你成功躲避该敌人，它解除交战状态但不横置。
你回合结束前，该敌人不能与你交战。

简化说明：
- activate() 消耗本卡并武装；随后由会话层发起躲避行动
  （lockpicks/burglary 同模式；若先做了其他检定，武装在
  SKILL_TEST_ENDS 时清除）。
- -2躲避以降低检定难度实现（SKILL_TEST_BEGINS 改写 ctx.difficulty）。
- "不横置"：引擎躲避成功会横置敌人，本卡在 ENEMY_EVADED 时将其重置。
- "不能与你交战"：引擎 ENEMY_ENGAGED 无取消窗口，采用事后校正——
  敌人与你交战时立即解除（放回地点）；你的回合结束时标记过期。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class Stealth(CardImplementation):
    card_id = "stealth_lv0"
    activations = [{
        "id": "evade",
        "label": "消耗：躲避（敌人-2躲避，成功不横置且不能再交战你）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False
        # {enemy_instance_id: investigator_id} 本回合不能再交战该调查员
        self._engagement_block: dict[str, str] = {}

    def activate(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        inst.exhausted = True
        self._armed = True
        return True

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def lower_evade(self, ctx):
        """本次躲避尝试所选敌人-2躲避（以降低难度实现）。"""
        if not self._armed or ctx.skill_type != Skill.AGILITY:
            return
        if ctx.difficulty is not None:
            ctx.difficulty = max(0, ctx.difficulty - 2)
            ctx.extra["stealth_lowered"] = True

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.AFTER)
    def no_exhaust_and_block(self, ctx):
        """成功躲避：敌人解除交战但不横置；你回合结束前不能与你交战。"""
        if not self._armed:
            return
        enemy = ctx.game_state.get_card_instance(ctx.enemy_id)
        if enemy is None:
            return
        enemy.exhausted = False
        self._engagement_block[ctx.enemy_id] = ctx.investigator_id
        ctx.extra["stealth_no_exhaust"] = ctx.enemy_id
        ctx.game_state.log_effect("🥷 潜行：敌人未被横置，且本回合不能再与你交战")

    @on_event(GameEvent.ENEMY_ENGAGED, priority=TimingPriority.WHEN)
    def prevent_engagement(self, ctx):
        """被标记敌人与你交战时：立即解除（事后校正，引擎无取消窗口）。"""
        if ctx.enemy_id not in self._engagement_block:
            return
        if self._engagement_block[ctx.enemy_id] != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or ctx.enemy_id not in inv.threat_area:
            return
        inv.threat_area.remove(ctx.enemy_id)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and ctx.enemy_id not in loc.enemies:
            loc.enemies.append(ctx.enemy_id)
        ctx.extra["stealth_engagement_prevented"] = ctx.enemy_id

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def expire_block(self, ctx):
        """你的回合结束：交战禁止标记过期。"""
        self._engagement_block = {
            eid: iid for eid, iid in self._engagement_block.items()
            if iid != ctx.investigator_id
        }

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
