"""Bloodlust (Level 0) — Neutral Treachery, Weakness. Bonded (The Hungering Blade).
显现：从嗜血之刃上移除2个献祭，将嗜血附着到其上。若不能，受到1点恐惧
并将嗜血洗回你的牌组。
[fast] 当你以嗜血之刃攻击时，将嗜血洗入你的牌组：本次攻击造成+1伤害。
（每次攻击限1次。）

简化说明：
- 嗜血之刃（the_hungering_blade_lv1）的献祭以 uses["offerings"] 计数。
- 附着实现为：嗜血实例留在 cards_in_play，attached_to 指向刀刃实例。
- [fast]加伤自动触发（官方为玩家选择支付"洗回牌组"费用）：以嗜血之刃
  攻击造成伤害时自动洗回并+1伤害（每次攻击限1次，SKILL_TEST_BEGINS 重置）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_BLADE_ID = "the_hungering_blade_lv1"
_OFFERINGS_COST = 2


class Bloodlust(CardImplementation):
    card_id = "bloodlust_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_attack = False

    def _find_blade(self, game_state):
        """在场上的嗜血之刃实例（任意调查员控制）。"""
        for inst in game_state.cards_in_play.values():
            if inst.card_id == _BLADE_ID:
                return inst
        return None

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != "bloodlust_lv0":
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if "bloodlust_lv0" in inv.hand:
            inv.hand.remove("bloodlust_lv0")

        blade = self._find_blade(ctx.game_state)
        if blade is not None and blade.uses.get("offerings", 0) >= _OFFERINGS_COST:
            blade.uses["offerings"] -= _OFFERINGS_COST
            from backend.models.state import CardInstance
            inst_id = ctx.game_state.next_instance_id()
            ci = CardInstance(
                instance_id=inst_id,
                card_id="bloodlust_lv0",
                owner_id=ctx.investigator_id,
                controller_id=ctx.investigator_id,
                attached_to=blade.instance_id,
            )
            ctx.game_state.cards_in_play[inst_id] = ci
            ctx.extra["bloodlust_attached"] = blade.instance_id
            ctx.game_state.log_effect("🩸 嗜血：移除2献祭，附着到嗜血之刃")
        else:
            inv.horror += 1  # 直接恐惧（不分配）
            inv.deck.append("bloodlust_lv0")
            random.shuffle(inv.deck)
            ctx.extra["bloodlust_shuffled_back"] = True
            ctx.game_state.log_effect(
                "🩸 嗜血：无法支付献祭，受1点恐惧并洗回牌组")

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reset_attack_limit(self, ctx):
        self._used_this_attack = False

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """以嗜血之刃攻击时：自动洗回嗜血，+1伤害（每次攻击限1次）。"""
        if self._used_this_attack:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.card_id != "bloodlust_lv0":
            # 抽到时的临时注册 id 与附着实例 id 不同：按 card_id 兜底扫描
            inst = next(
                (c for c in ctx.game_state.cards_in_play.values()
                 if c.card_id == "bloodlust_lv0"),
                None,
            )
        if inst is None or inst.card_id != "bloodlust_lv0":
            return
        if inst.attached_to is None or ctx.source != inst.attached_to:
            return
        blade = ctx.game_state.get_card_instance(inst.attached_to)
        if blade is None or blade.card_id != _BLADE_ID:
            return

        self._used_this_attack = True
        ctx.modify_amount(1, "bloodlust_bonus_damage")

        # 洗回持有者牌组
        owner = ctx.game_state.get_investigator(inst.owner_id)
        if owner is not None:
            owner.deck.append("bloodlust_lv0")
            random.shuffle(owner.deck)
        ctx.game_state.cards_in_play.pop(inst.instance_id, None)
        ctx.extra["bloodlust_shuffled_for_damage"] = True
        ctx.game_state.log_effect("🩸 嗜血：洗回牌组，本次攻击+1伤害")
