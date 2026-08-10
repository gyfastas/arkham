"""Kleptomania (Level 0) — Neutral Asset, Basic Weakness.
仅多人游戏。
显现 - 将偷窃癖放入你的战场。
[action]：夺取你所在地点另一位调查员的1个[[Item]]支援或2资源。
然后，将偷窃癖洗入你的牌组。
强制 - 在你的回合结束时：受到1点恐惧。

简化说明：
- 显现放入战场（play_area），实例经 card_id 扫描定位（同 chronophobia）。
- [action] 实现为 activate()：目标默认你所在地点的第一位其他调查员；
  默认夺取2资源，传 asset_instance_id 时改为夺取该 Item 支援的控制权
  （玩家选择 UI 需会话层接线）。
- 回合结束的恐惧为直接恐惧（不分配）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Kleptomania(CardImplementation):
    card_id = "kleptomania_lv0"
    activations = [{
        "id": "steal",
        "label": "[行动] 夺取同地点调查员1个Item或2资源，洗回牌组",
        "method": "activate",
        "actions": 1,
    }]

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "kleptomania_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "kleptomania_lv0" in inv.hand:
            inv.hand.remove("kleptomania_lv0")

        from backend.models.state import CardInstance
        inst_id = ctx.game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="kleptomania_lv0",
            owner_id=ctx.investigator_id,
            controller_id=ctx.investigator_id,
        )
        ctx.game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def end_of_turn_horror(self, ctx):
        """强制 - 你的回合结束时：受到1点恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if self._find_kleptomania(ctx.game_state, inv) is None:
            return
        inv.horror += 1  # 直接恐惧

    def activate(self, game_state, investigator_id,
                 target_investigator_id: str | None = None,
                 asset_instance_id: str | None = None) -> bool:
        """[action] 夺取同地点另一位调查员的1个Item支援或2资源，洗回牌组。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = self._find_kleptomania(game_state, inv)
        if inst is None:
            return False

        # 目标：同地点的另一调查员（默认第一位）
        target = None
        if target_investigator_id is not None:
            t = game_state.get_investigator(target_investigator_id)
            if t is not None and t.investigator_id != inv.investigator_id \
                    and t.location_id == inv.location_id:
                target = t
        else:
            for other in game_state.investigators.values():
                if other.investigator_id != inv.investigator_id \
                        and other.location_id == inv.location_id:
                    target = other
                    break
        if target is None:
            return False

        if asset_instance_id is not None:
            # 夺取 Item 支援控制权
            item = game_state.get_card_instance(asset_instance_id)
            data = game_state.get_card_data(item.card_id) if item else None
            if item is None or data is None or "item" not in (data.traits or []):
                return False
            if asset_instance_id not in target.play_area:
                return False
            target.play_area.remove(asset_instance_id)
            item.controller_id = inv.investigator_id
            inv.play_area.append(asset_instance_id)
            game_state.log_effect(
                f"🤑 偷窃癖：夺取【{game_state.card_name(item.card_id)}】的控制权"
            )
        else:
            if target.resources < 2:
                return False
            target.resources -= 2
            inv.resources += 2
            game_state.log_effect("🤑 偷窃癖：夺取2资源")

        # 洗入你的牌组
        inv.play_area.remove(inst.instance_id)
        game_state.cards_in_play.pop(inst.instance_id, None)
        inv.deck.append("kleptomania_lv0")
        random.shuffle(inv.deck)
        return True

    @staticmethod
    def _find_kleptomania(game_state, inv):
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "kleptomania_lv0":
                return inst
        return None
