"""Detached from Reality (Level 0) — Neutral Treachery, Weakness.
显现：若梦之门（奇妙旅程）已在场，将其翻面。否则，从你的绑定卡中搜寻
梦之门（虚无现实）并放置入场。无论哪种情况，与你交战的每个敌人解除交战，
你移动到梦之门。

简化说明：
- 引擎无双面卡翻面与绑定卡存储（引擎缺口）：翻面记入
  scenario.vars["dream_gate_flipped"]；梦之门不在场时，若其地点数据已注册
  （dream_gate_lv0），直接创建 LocationState 放置入场。
- 解除交战：交战敌人移回你原地点的未交战列表，然后你移动到梦之门。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_DREAM_GATE_ID = "dream_gate_lv0"


class DetachedFromReality(CardImplementation):
    card_id = "detached_from_reality_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "detached_from_reality_lv0":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "detached_from_reality_lv0" in inv.hand:
            inv.hand.remove("detached_from_reality_lv0")

        if _DREAM_GATE_ID in game_state.locations:
            # 已在场：翻面（奇妙旅程 <-> 虚无现实）
            flipped = game_state.scenario.vars.get("dream_gate_flipped", False)
            game_state.scenario.vars["dream_gate_flipped"] = not flipped
            ctx.extra["detached_from_reality_flipped"] = True
            game_state.log_effect("🌀 脱离现实：梦之门翻面")
        else:
            # 放置梦之门入场（数据已注册时）
            gate_data = game_state.get_card_data(_DREAM_GATE_ID)
            if gate_data is not None:
                from backend.models.state import LocationState
                game_state.locations[_DREAM_GATE_ID] = LocationState(
                    location_id=_DREAM_GATE_ID,
                    card_data=gate_data,
                    revealed=True,
                )
                game_state.scenario.vars["dream_gate_flipped"] = True  # 虚无现实面
                ctx.extra["detached_from_reality_entered"] = True
                game_state.log_effect("🌀 脱离现实：梦之门放置入场")

        if _DREAM_GATE_ID not in game_state.locations:
            inv.discard.append("detached_from_reality_lv0")
            return

        # 解除交战：敌人移回原地点的未交战列表
        old_loc = game_state.get_location(inv.location_id)
        for enemy_id in list(inv.threat_area):
            enemy = game_state.get_card_instance(enemy_id)
            enemy_data = (
                game_state.get_card_data(enemy.card_id) if enemy else None
            )
            if enemy_data is None or enemy_data.type.value != "enemy":
                continue
            inv.threat_area.remove(enemy_id)
            if old_loc is not None:
                old_loc.enemies.append(enemy_id)

        # 移动到梦之门
        inv.location_id = _DREAM_GATE_ID
        ctx.extra["detached_from_reality_moved"] = True

        inv.discard.append("detached_from_reality_lv0")
