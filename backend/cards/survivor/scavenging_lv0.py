"""Scavenging (Level 0) — Survivor Asset.
反应 - 在你成功调查并超过难度2点或以上后：弃置拾荒，从你的弃牌堆中将一张道具支援卡加入你的手牌。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class Scavenging(CardImplementation):
    card_id = "scavenging_lv0"

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def scavenge_item(self, ctx):
        if ctx.skill_type != Skill.INTELLECT:
            return
        if (ctx.modified_skill or 0) - (ctx.difficulty or 0) < 2:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return

        # 从弃牌堆找第一张道具支援卡
        found = None
        for cid in inv.discard:
            cd = ctx.game_state.get_card_data(cid)
            if cd is not None and cd.type == CardType.ASSET and "item" in (cd.traits or []):
                found = cid
                break
        if found is None:
            return

        # 弃置拾荒，取回道具
        inv.play_area.remove(self.instance_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.remove(found)
        inv.hand.append(found)
        # 拾荒自身进入弃牌堆（在取回之后，避免被立即取回）
        inv.discard.append("scavenging_lv0")
        ctx.extra["scavenging_recovered"] = found
