"""Dr. Elli Horowitz (Level 0) — Seeker Asset, Ally slot. (04021)
[反应]在艾莉·霍洛维茨博士入场后：检索你牌堆顶9张牌中的一张[[圣物]]支援
并附着到她身上。混洗你的牌堆。
附着于艾莉·霍洛维茨博士的每张[[圣物]]支援均不占用任何栏位（它仍被视为
在场且由你控制）。

简化说明：
- 检索目标自动取顶9张中第一张圣物支援（官方为玩家任选其中一张）；
- 附着的圣物直接以 CardInstance 入场（不占栏位即不占用 SlotManager），
  attached_to 指博士实例；其实现注册需会话层接线（与 miss_doyle 附身猫
  同款缺口：卡实现拿不到 Game.card_registry）；
- 未检到圣物时仅混洗牌堆。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance

SEARCH_DEPTH = 9


class DrElliHorowitz(CardImplementation):
    card_id = "dr_elli_horowitz_lv0"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def attach_relic(self, ctx):
        """入场后：检索牌堆顶9张，第一张圣物附着到博士身上，洗牌。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        top = list(inv.deck[:SEARCH_DEPTH])
        rest = list(inv.deck[SEARCH_DEPTH:])
        relic_id = None
        for cid in top:
            cd = ctx.game_state.get_card_data(cid)
            if (cd is not None and cd.type == CardType.ASSET
                    and "relic" in [t.lower() for t in (cd.traits or [])]):
                relic_id = cid
                break

        if relic_id is not None:
            top.remove(relic_id)
            self._put_relic_into_play(ctx, inv, relic_id)

        # 混洗牌堆（未选中的检索牌一并洗回）
        inv.deck = rest + top
        random.shuffle(inv.deck)

    def _put_relic_into_play(self, ctx, inv, relic_id: str) -> None:
        """圣物附着入场：不占栏位，仍视为在场且由你控制。"""
        cd = ctx.game_state.get_card_data(relic_id)
        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=relic_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            attached_to=self.instance_id,
            slot_used=[],  # 附着于博士：不占任何栏位
        )
        if cd and cd.uses:
            inst.uses = dict(cd.uses)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        ctx.extra["elli_attached_relic"] = relic_id
        ctx.game_state.log_effect(
            f"🔬 艾莉·霍洛维茨博士：附着【{ctx.game_state.card_name(relic_id)}】"
            "（不占栏位）"
        )
