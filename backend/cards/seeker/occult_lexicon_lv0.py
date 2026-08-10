"""Occult Lexicon (Level 0) — Seeker Asset, Hand slot. (05316)
每副牌组限制1张。
强制 - 在密教辞典入场后：在你的绑定卡牌中查找3张鲜血仪式。将其中1张
加入你的手牌并将其余2张混洗入你的牌堆。在密教辞典离场时，找出所有的
鲜血仪式（不论其是否在场）并将其放在一边，位于场外。

简化说明：
- 绑定卡池存 scenario.vars["bonded_cards"]（card_id 列表）；池内不足3张
  鲜血仪式时凭空补足（生产数据含 blood_rite_lv0；官方绑定卡随卡组带入，
  组牌流程暂无绑定池登记，引擎缺口）；
- 离场清理覆盖持有者的手牌/牌堆/弃牌堆（场上的鲜血仪式为事件卡，
  结算后即入弃牌堆，无需处理在场情形）；清理出的卡放回绑定卡池；
- 部分离场路径在注销本实现后才发 CARD_LEAVES_PLAY——此时清理不触发，
  已列入引擎缺口。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_BLOOD_RITE = "blood_rite_lv0"
_BONDED_VAR = "bonded_cards"


class OccultLexicon(CardImplementation):
    card_id = "occult_lexicon_lv0"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.FORCED)
    def fetch_blood_rites(self, ctx):
        """强制 - 入场后：绑定卡池找3张鲜血仪式，1张入手、2张洗入牌堆。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        bonded = ctx.game_state.scenario.vars.setdefault(_BONDED_VAR, [])
        copies = []
        while len(copies) < 3:
            if _BLOOD_RITE in bonded:
                bonded.remove(_BLOOD_RITE)
                copies.append(_BLOOD_RITE)
            else:
                copies.append(_BLOOD_RITE)  # 绑定池未登记：凭空补足

        inv.hand.append(copies[0])
        inv.deck.extend(copies[1:])
        random.shuffle(inv.deck)
        ctx.extra["occult_lexicon_fetched"] = len(copies)
        ctx.game_state.log_effect(
            "📕 密教辞典：1张鲜血仪式加入手牌，其余2张混洗入牌堆"
        )

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def set_aside_blood_rites(self, ctx):
        """离场时：找出所有鲜血仪式（手牌/牌堆/弃牌堆），放在一边位于场外。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        bonded = ctx.game_state.scenario.vars.setdefault(_BONDED_VAR, [])
        found = 0
        for zone in (inv.hand, inv.deck, inv.discard):
            while _BLOOD_RITE in zone:
                zone.remove(_BLOOD_RITE)
                bonded.append(_BLOOD_RITE)
                found += 1
        if found:
            ctx.extra["occult_lexicon_set_aside"] = found
            ctx.game_state.log_effect(
                f"📕 密教辞典：离场，{found}张鲜血仪式放在一边（场外）"
            )
