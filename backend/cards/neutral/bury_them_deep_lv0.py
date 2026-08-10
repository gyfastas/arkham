"""Bury Them Deep (Level 0) — Neutral Event, Signature (William Yorick).
快速。你所在地点中1个非[[精英]]敌人被击败后打出。
将该敌人（与本卡牌）放入胜利牌区。

简化说明：
- 从手牌自动触发：你所在地点的非精英敌人被击败时自动打出（官方为玩家
  自行选择打出时机；与 lucky_lv0 的自动打出简化一致）。
- 引擎在敌人被击败后会将其卡 id 追加到遭遇弃牌堆（damage._remove_enemy_from_play），
  胜利牌区中的记录用于计分，该残余不受影响。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class BuryThemDeep(CardImplementation):
    card_id = "bury_them_deep_lv0"

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def add_to_victory(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        enemy_card_id = ctx.extra.get("card_id")
        enemy_data = ctx.game_state.get_card_data(enemy_card_id)
        if enemy_data is not None and "elite" in (enemy_data.traits or []):
            return
        # 你所在地点：与你交战，或在你所在地点未交战
        engaged = ctx.target in inv.threat_area
        location = ctx.game_state.get_location(inv.location_id)
        at_location = location is not None and ctx.target in location.enemies
        if not (engaged or at_location):
            return

        inv.hand.remove(self.card_id)
        ctx.game_state.scenario.victory_display.append(enemy_card_id)
        ctx.game_state.scenario.victory_display.append(self.card_id)
        ctx.extra["bury_them_deep"] = enemy_card_id
        ctx.game_state.log_effect(
            f"⚰️ 深埋：【{ctx.game_state.card_name(enemy_card_id)}】与本卡放入胜利牌区"
        )
