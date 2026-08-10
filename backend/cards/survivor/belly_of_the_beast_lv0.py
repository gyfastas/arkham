"""Belly of the Beast (Level 0) — Survivor Event.
快速。在你成功躲避一名敌人且超过难度至少2点后打出。
发现该敌人所在地点的1个线索。

简化说明：
- 从手牌自动打出（persistent_in_hand）：SKILL_TEST_SUCCESSFUL 记录敏捷
  检定的超出值，ENEMY_EVADED 时若超出值≥2且资源足够，自动支付1资源打出。
- 引擎的躲避流程不区分"躲避检定"与其他敏捷检定，超出值快照取自最近一次
  敏捷检定成功——ENEMY_EVADED 仅由躲避成功触发，时序上即该次检定。
- 敌人所在地点：躲避成功后敌人留在调查员所在地点（引擎行为），线索直接从
  该地点取得（地点无线索时不发现，与官方一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class BellyOfTheBeast(CardImplementation):
    card_id = "belly_of_the_beast_lv0"
    persistent_in_hand = True  # 在手牌中持续监听躲避成功窗口

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {investigator_id: margin} 最近一次敏捷检定成功的超出值
        self._margins: dict[str, int] = {}

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def snapshot_margin(self, ctx):
        if ctx.skill_type != Skill.AGILITY:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        self._margins[ctx.investigator_id] = margin

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.WHEN)
    def discover_clue(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        if self._margins.get(ctx.investigator_id, 0) < 2:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return

        # 敌人所在地点（默认调查员所在地点）
        loc = ctx.game_state.get_location(inv.location_id)
        if ctx.enemy_id:
            for cand in ctx.game_state.locations.values():
                if ctx.enemy_id in cand.enemies:
                    loc = cand
                    break
        if loc is None or loc.clues < 1:
            return

        # 自动打出
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        loc.clues -= 1
        inv.clues += 1
        ctx.extra["belly_of_the_beast_clue"] = loc.location_id
        ctx.game_state.log_effect(
            f"🐍 兽腹之中：躲避超出2点，发现【{loc.card_data.name_cn or loc.location_id}】1个线索")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._margins.pop(ctx.investigator_id, None)
