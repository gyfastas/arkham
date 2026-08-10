"""Anna Kaslow (Level 4) — Neutral Asset, Ally.
你拥有2个额外塔罗槽。
[reaction] 当游戏开始时，若安娜·卡斯洛在你的起始手牌中：将她放置入场。
[reaction] 安娜·卡斯洛入场后：从你的牌组中搜寻1张[[Tarot]]支援并放置入场。

简化说明：
- 额外塔罗槽经 SlotManager.add_bonus(TAROT, 2) 实现（CARD_ENTERS_PLAY 时
  授予，CARD_LEAVES_PLAY 时移除；与 charisma 的槽位通道一致）。
- 搜寻塔罗自动选牌组中第一张带 tarot 词条的支援（官方为玩家搜寻自选），
  放置入场不支付费用（卡面未要求支付）；剩余牌组洗牌。
- 游戏开始时的入场由会话层调用 put_into_play_at_game_begin()（引擎无
  GAME_BEGINS 事件——缺口）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class AnnaKaslow(CardImplementation):
    card_id = "anna_kaslow_lv4"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def on_enters_play(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.card_id != "anna_kaslow_lv4":
            return
        game_state = ctx.game_state
        inv = game_state.get_investigator(inst.owner_id)
        if inv is None:
            return

        # 2个额外塔罗槽
        slot_mgr = getattr(game_state, "slot_managers", {}).get(inst.owner_id)
        if slot_mgr is not None:
            slot_mgr.add_bonus(SlotType.TAROT, 2)

        # 搜寻牌组中第一张塔罗支援，放置入场
        tarot_idx = None
        for i, cid in enumerate(inv.deck):
            cd = game_state.get_card_data(cid)
            if cd is not None and "tarot" in (cd.traits or []):
                tarot_idx = i
                break
        if tarot_idx is None:
            return
        tarot_id = inv.deck.pop(tarot_idx)
        random.shuffle(inv.deck)

        from backend.models.state import CardInstance
        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id=tarot_id,
            owner_id=inst.owner_id,
            controller_id=inst.owner_id,
        )
        game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)
        ctx.extra["anna_kaslow_tarot"] = tarot_id
        game_state.log_effect(
            f"🔮 安娜·卡斯洛：【{game_state.card_name(tarot_id)}】放置入场")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def on_leaves_play(self, ctx):
        """离场时移除2个额外塔罗槽。"""
        if ctx.extra.get("card_id") != "anna_kaslow_lv4":
            return
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            ctx.investigator_id)
        if slot_mgr is not None:
            slot_mgr.remove_bonus(SlotType.TAROT, 2)

    def put_into_play_at_game_begin(self, game_state, investigator_id) -> bool:
        """[reaction] 游戏开始时在起始手牌中：放置入场（会话层调用，免费用）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or "anna_kaslow_lv4" not in inv.hand:
            return False
        inv.hand.remove("anna_kaslow_lv4")
        from backend.models.state import CardInstance
        inst_id = game_state.next_instance_id()
        ci = CardInstance(
            instance_id=inst_id,
            card_id="anna_kaslow_lv4",
            owner_id=investigator_id,
            controller_id=investigator_id,
        )
        game_state.cards_in_play[inst_id] = ci
        inv.play_area.append(inst_id)
        return True
