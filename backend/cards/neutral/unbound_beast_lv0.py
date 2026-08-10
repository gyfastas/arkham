"""Unbound Beast (Level 0) — Neutral Enemy, Weakness. 绑定（受召猎犬）。
猎物 - 承受者。猎手。反击。
显现 - 如果场上没有受召猎犬（Summoned Hound），将脱缰野兽放在一边，
位于场外。否则，将一位调查员的受召猎犬放在一边（位于场外），并且生成
脱缰野兽并与该调查员交战。

官方数值（arkhamdb 06283，玩家卡 JSON 通道不含 enemy_* 字段，需会话/数据
层接线；测试以 make_enemy_data 注入）：战斗3 / 生命3 / 躲避3 / 伤害1 / 恐惧1。

简化说明：
- "放在一边，位于场外"记入 scenario.vars["set_aside_out_of_play"]
  （卡 id 列表；引擎无独立搁置区）。
- 受召猎犬的数据 id 为 summoned_hound_lv1（mystic）；按 card_id 前缀
  "summoned_hound" 匹配以兼容可能的其它等级。
- 猎物/猎手/反击关键词依赖敌人 AI 与交战通道，引擎缺口。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class UnboundBeast(CardImplementation):
    card_id = "unbound_beast_lv0"

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "unbound_beast_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "unbound_beast_lv0" in inv.hand:
            inv.hand.remove("unbound_beast_lv0")

        game_state = ctx.game_state
        set_aside = game_state.scenario.vars.setdefault("set_aside_out_of_play", [])

        # 查找场上的受召猎犬
        hound = None
        for ci in game_state.cards_in_play.values():
            if ci.card_id.startswith("summoned_hound"):
                hound = ci
                break

        if hound is None:
            # 场上没有受召猎犬：本卡搁置，位于场外
            set_aside.append("unbound_beast_lv0")
            game_state.log_effect("🐺 脱缰野兽：场上无受召猎犬，搁置在场外")
            ctx.extra["unbound_beast_set_aside"] = True
            return

        # 将受召猎犬搁置在场外（从其持有者场上移除）
        owner = game_state.get_investigator(hound.owner_id)
        game_state.cards_in_play.pop(hound.instance_id, None)
        if owner is not None and hound.instance_id in owner.play_area:
            owner.play_area.remove(hound.instance_id)
        slot_mgr = getattr(game_state, "slot_managers", {}).get(hound.owner_id)
        if slot_mgr is not None:
            slot_mgr.vacate(hound.instance_id)
        set_aside.append(hound.card_id)

        # 生成脱缰野兽并与该调查员交战
        target_inv = owner if owner is not None else inv
        inst_id = game_state.next_instance_id()
        beast = CardInstance(
            instance_id=inst_id,
            card_id="unbound_beast_lv0",
            owner_id=target_inv.investigator_id,  # 承受者（猎物判定用）
            controller_id="scenario",
        )
        game_state.cards_in_play[inst_id] = beast
        target_inv.threat_area.append(inst_id)

        game_state.log_effect(
            f"🐺 脱缰野兽：受召猎犬被搁置，脱缰野兽生成并与"
            f"【{target_inv.investigator_id}】交战")
        ctx.extra["unbound_beast_spawned"] = inst_id
