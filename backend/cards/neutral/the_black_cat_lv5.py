"""The Black Cat (Level 5) — Neutral Asset, Ally slot. (06285)
每当你在技能检定中揭示[石板]、[古神]或[远古印记]符号时，你可以选择使用
以下效果代替该符号的正常效果：
[石板]：-1。黑猫受到1点直接伤害。
[古神]：-1。黑猫受到1点直接恐惧。
[远古印记]：+5。治疗黑猫上所有伤害和恐惧。

简化说明：
- "可以选择"为自动选择：[远古印记]总是替换（+5通常远优于剧本效果）；
  [石板]/[古神]仅在不致黑猫被击败时替换（玩家不会选择自杀性替换）。
- 符号的"正常效果"为剧本相关值，引擎按0处理（CHAOS_TOKEN_VALUES 中符号
  标记为 None→0），替换即把修正值改写为 -1/+5。
- 直接伤害/恐惧不经分配通道，直接加到实例上；黑猫因此达到上限会被击败
  （自动选择已规避该情形，仍兜底走 ASSET_DEFEATED 流程）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class TheBlackCat(CardImplementation):
    card_id = "the_black_cat_lv5"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def replace_symbol(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        cd = ctx.game_state.get_card_data("the_black_cat_lv5")
        health = getattr(cd, "health", None) or 3
        sanity = getattr(cd, "sanity", None) or 3

        token = ctx.chaos_token
        if token == ChaosTokenType.ELDER_SIGN:
            # +5，治疗黑猫上所有伤害和恐惧
            ctx.modify_amount(5 - ctx.amount, "black_cat_elder_sign")
            inst.damage = 0
            inst.horror = 0
            ctx.extra["black_cat_replaced"] = "elder_sign"
        elif token == ChaosTokenType.TABLET:
            # -1，黑猫受1点直接伤害（会致败则不替换）
            if inst.damage + 1 >= health:
                return
            ctx.modify_amount(-1 - ctx.amount, "black_cat_tablet")
            inst.damage += 1
            ctx.extra["black_cat_replaced"] = "tablet"
        elif token == ChaosTokenType.ELDER_THING:
            # -1，黑猫受1点直接恐惧（会致败则不替换）
            if inst.horror + 1 >= sanity:
                return
            ctx.modify_amount(-1 - ctx.amount, "black_cat_elder_thing")
            inst.horror += 1
            ctx.extra["black_cat_replaced"] = "elder_thing"
