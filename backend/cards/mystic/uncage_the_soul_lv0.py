"""Uncage the Soul (Level 0) — Mystic Event. (03033)
打出你手牌中的一张[[法术]]或[[仪式]]卡，其资源费用降低3点。

简化说明：
- 目标自动选择：手牌中第一张法术/仪式卡（无选择 UI）；可用
  ctx.extra["play_card_id"] 指定。
- 支援卡：支付 max(0, 费用-3) 后直接放入场地（建实例、占用槽位、初始化
  uses）。CARD_ENTERS_PLAY 不补发（卡牌代码拿不到事件总线）。
- 已知限制（引擎缺口）：卡牌代码拿不到 CardRegistry，被打出支援的
  CardImplementation 不会随之注册（其持续能力待会话层/引擎提供
  "从手牌打出"入口后生效）；事件/技能类法术卡不自动结算效果，直接入弃牌堆。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class UncageTheSoul(CardImplementation):
    card_id = "uncage_the_soul_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def play_reduced(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        target_id = ctx.extra.get("play_card_id")
        if target_id is None:
            for cid in inv.hand:
                if self._is_spell_or_ritual(ctx, cid):
                    target_id = cid
                    break
        if target_id is None or target_id not in inv.hand:
            return
        if not self._is_spell_or_ritual(ctx, target_id):
            return

        cd = ctx.game_state.get_card_data(target_id)
        cost = max(0, (cd.cost or 0) - 3)
        if inv.resources < cost:
            return

        inv.resources -= cost
        inv.hand.remove(target_id)
        ctx.extra["uncage_the_soul_played"] = target_id
        ctx.extra["uncage_the_soul_cost_paid"] = cost

        if cd.type != CardType.ASSET:
            # 事件/技能：效果不自动结算（引擎缺口），入弃牌堆
            inv.discard.append(target_id)
            ctx.game_state.log_effect(
                f"🕊️ 灵魂释放：【{ctx.game_state.card_name(target_id)}】"
                f"以{cost}资源打出（效果需手动结算）")
            return

        # 支援卡：放入场地
        instance_id = ctx.game_state.next_instance_id()
        inst = CardInstance(
            instance_id=instance_id,
            card_id=target_id,
            owner_id=inv.investigator_id,
            controller_id=inv.investigator_id,
            slot_used=list(cd.slots or []),
        )
        if cd.uses:
            inst.uses = dict(cd.uses)
        slot_mgr = getattr(ctx.game_state, "slot_managers", {}).get(
            inv.investigator_id)
        if slot_mgr is not None and cd.slots:
            slot_mgr.occupy(instance_id, cd.slots, cd.traits)
        ctx.game_state.cards_in_play[instance_id] = inst
        inv.play_area.append(instance_id)
        ctx.extra["uncage_the_soul_instance"] = instance_id
        ctx.game_state.log_effect(
            f"🕊️ 灵魂释放：以{cost}资源打出【{ctx.game_state.card_name(target_id)}】")
        # 注：卡牌代码拿不到事件总线，CARD_ENTERS_PLAY 不补发（引擎缺口）。

    def _is_spell_or_ritual(self, ctx, card_id: str) -> bool:
        cd = ctx.game_state.get_card_data(card_id)
        traits = [t.lower() for t in (cd.traits or [])] if cd else []
        return "spell" in traits or "ritual" in traits
