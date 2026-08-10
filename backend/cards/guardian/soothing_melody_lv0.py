"""Soothing Melody (Level 0) — Guardian Event. (05314)
绑定(圣化之镜)。治愈你所在地点的调查员和/或[[盟友]]支援卡的2点伤害或2恐惧
(或者以任意方式组合，总计2点)。抽取1张卡牌。

简化说明：
- 治愈分配自动选择：优先治愈打出者本人的伤害，再治愈恐惧（官方为玩家在
  同地点调查员/盟友间任意分配）。会话层可经 ctx.extra["heal_plan"] 指定
  [{"target": "self"|investigator_id|instance_id, "kind": "damage"|"horror",
  "amount": n}]，总计2点。
- 绑定(圣化之镜)的牌组构建规则不在效果实现范围。
- 抽牌直接操作牌库顶（不经 CARD_DRAWN 钩子）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_TOTAL = 2


class SoothingMelody(CardImplementation):
    card_id = "soothing_melody_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        """打出后：治愈共2点伤害/恐惧，然后抽1张牌。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        plan = ctx.extra.get("heal_plan")
        if plan:
            healed = self._apply_plan(ctx.game_state, inv, plan)
        else:
            healed = self._auto_heal(inv)

        drawn = None
        if inv.deck:
            drawn = inv.deck.pop(0)
            inv.hand.append(drawn)

        ctx.extra["soothing_melody_healed"] = healed
        ctx.extra["soothing_melody_drew"] = drawn
        ctx.game_state.log_effect(
            f"🎵 舒缓旋律：治愈{healed}点伤害/恐惧，抽取1张卡牌")

    @staticmethod
    def _auto_heal(inv) -> int:
        """自动分配：先治愈伤害，再治愈恐惧（总计至多2点）。"""
        healed_damage = min(_TOTAL, inv.damage)
        inv.damage -= healed_damage
        healed_horror = min(_TOTAL - healed_damage, inv.horror)
        inv.horror -= healed_horror
        return healed_damage + healed_horror

    @staticmethod
    def _apply_plan(game_state, inv, plan) -> int:
        """按会话层给出的分配方案治愈（同地点校验在此从简）。"""
        healed = 0
        for entry in plan[:_TOTAL]:
            if healed >= _TOTAL:
                break
            kind = entry.get("kind")
            amount = min(int(entry.get("amount", 1) or 1), _TOTAL - healed)
            target = entry.get("target", "self")
            if target == "self" or target == inv.investigator_id:
                card = inv
            else:
                card = game_state.get_investigator(target)
                if card is None:
                    card = game_state.get_card_instance(target)
            if card is None:
                continue
            if kind == "damage":
                actual = min(amount, card.damage)
                card.damage -= actual
            else:
                actual = min(amount, card.horror)
                card.horror -= actual
            healed += actual
        return healed
