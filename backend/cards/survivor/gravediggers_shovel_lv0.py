"""Gravedigger's Shovel (Level 0) — Survivor Asset, Hand slot.
[action]：攻击。本次攻击中你+2战斗。
[action] 丢弃挖墓人的铲子：发现你所在地点的1个线索。

简化说明：
- 攻击加值在以本武器发起的战斗（ctx.source 为铲子）中生效。
- 发现线索为启动能力（activations 声明，1行动）：丢弃铲子并将所在地点
  1个线索移给调查员；不另发 CLUE_DISCOVERED 事件（与既有弃牌换效果
  实现一致，从简）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class GravediggersShovel(CardImplementation):
    card_id = "gravediggers_shovel_lv0"
    activations = [{
        "id": "discover_clue",
        "label": "丢弃铲子：发现所在地点1个线索",
        "method": "activate_discover_clue",
        "actions": 1,
    }]

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """以铲子攻击时 +2 战斗。"""
        if ctx.source != self.instance_id:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "gravediggers_shovel_combat")

    def activate_discover_clue(self, game_state, investigator_id: str) -> bool:
        """[action] 丢弃铲子：发现你所在地点的1个线索。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        loc = game_state.get_location(inv.location_id)
        if loc is None or loc.clues <= 0:
            return False

        # 丢弃铲子
        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)

        # 发现1个线索
        loc.clues -= 1
        inv.clues += 1
        game_state.log_effect("⛏️ 挖墓人的铲子：丢弃，发现所在地点1个线索")
        return True
