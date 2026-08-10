"""Miss Doyle (Level 1) — Survivor Asset, Ally slot. (06030)
Limit 1 per deck.
Forced - After Miss Doyle enters play: Search your bonded cards for Hope,
Zeal, and Augur. Randomly choose 1 to put into play and shuffle the other
2 into your deck. When Miss Doyle leaves play, find each of those assets
(even if they are out of play) and set them aside, out of play.

简化说明：
- "随机选1张"简化为按固定顺序取数据已注册的第一张（hope > zeal > augur）。
- 放置入场复刻 _play_asset 流程（自建 CardInstance + CARD_ENTERS_PLAY；
  猫的实现注册需会话层接线，同 a_chance_encounter 缺口）。
- 离场扫尾：在场/手牌/牌库/弃牌堆中的猫全部移出游戏
  （scenario.vars["out_of_play"]）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance

_BONDED = ("hope_lv0", "zeal_lv0", "augur_lv0")


class MissDoyle(CardImplementation):
    card_id = "miss_doyle_lv1"

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def summon_bonded_cat(self, ctx):
        """入场后：1只羁绊猫放置入场，其余2只洗入牌库。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        available = [cid for cid in _BONDED
                     if ctx.game_state.get_card_data(cid) is not None]
        if not available:
            return
        chosen = available[0]  # 简化：固定顺序而非随机
        rest = [cid for cid in _BONDED if cid != chosen]

        cd = ctx.game_state.get_card_data(chosen)
        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=chosen,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(cd.slots or []),
        )
        if cd.uses:
            inst.uses = dict(cd.uses)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr and cd.slots:
            slot_mgr.occupy(instance_id, cd.slots, cd.traits)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)

        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.CARD_ENTERS_PLAY,
                investigator_id=inv.investigator_id,
                target=instance_id,
                extra={"card_id": chosen},
            ))

        inv.deck.extend(rest)
        random.shuffle(inv.deck)
        ctx.extra["miss_doyle_cat"] = chosen
        ctx.game_state.log_effect(
            f"🐈 多伊尔小姐：【{ctx.game_state.card_name(chosen)}】入场，"
            "其余羁绊猫洗入牌库")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def set_aside_on_leave(self, ctx):
        """离场时：所有羁绊猫（无论何在）移出游戏。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            # 持有者兜底：从 owner_id 找
            inst = ctx.game_state.get_card_instance(self.instance_id)
            inv = ctx.game_state.get_investigator(
                getattr(inst, "owner_id", "") or "")
        if inv is None:
            return
        out = ctx.game_state.scenario.vars.setdefault("out_of_play", [])
        for cid in _BONDED:
            # 在场实例
            for iid in list(inv.play_area):
                ci = ctx.game_state.get_card_instance(iid)
                if ci is not None and ci.card_id == cid:
                    inv.play_area.remove(iid)
                    ctx.game_state.cards_in_play.pop(iid, None)
                    out.append(cid)
            # 手牌/牌库/弃牌堆
            for zone in (inv.hand, inv.deck, inv.discard):
                while cid in zone:
                    zone.remove(cid)
                    out.append(cid)
        ctx.game_state.log_effect("🐈 多伊尔小姐离场：羁绊猫移出游戏")
