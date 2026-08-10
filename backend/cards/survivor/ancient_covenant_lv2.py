"""Ancient Covenant (Level 2) — Survivor Asset. Permanent.
永久。每副牌组限制1张[[圣约]]。
[反应] 你所在地点的一位调查员在技能检定中结算一个[祝福]标记时，
消耗古代圣约：不要为该祝福标记的效果额外揭示标记。

简化说明：
- 引擎中祝福标记仅提供+2修正，并未实现"额外揭示一个标记"的官方规则
  （引擎缺口），故本卡效果为声明式：消耗本卡并在 ctx.extra 标记
  "ancient_covenant_no_extra_reveal"，供引擎/会话层在实现祝福额外揭示后消费。
- 永久（Permanent）为开局放置规则，由牌组/开局流程处理，本实现不含。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class AncientCovenant(CardImplementation):
    card_id = "ancient_covenant_lv2"

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.REACTION)
    def seal_bless_extra_reveal(self, ctx):
        """同地点调查员结算祝福标记时：消耗本卡，阻止额外揭示。"""
        if ctx.chaos_token != ChaosTokenType.BLESS:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.owner_id)
        performer = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or performer is None:
            return
        if self.instance_id not in owner.play_area:
            return
        if performer.location_id != owner.location_id:
            return
        inst.exhausted = True
        ctx.extra["ancient_covenant_no_extra_reveal"] = True
        ctx.game_state.log_effect(
            "📜 古代圣约：消耗，祝福标记不再额外揭示标记")
