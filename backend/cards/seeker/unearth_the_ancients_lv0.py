"""Unearth the Ancients (Level 0) — Seeker Event. (04024)
调查。选择你手牌中的1张[seeker]支援卡。本次技能检定难度等于所选
支援卡上打印的费用。如果成功，不发现线索，改为将该支援卡放置入场。
如果该支援卡带有[[遗物]]属性，抽1张牌。

简化说明：
- 检定由卡牌自身回放（CardSelfTest，无投入窗口；完整投入流程需会话层
  接线）；"Investigate."的行动属性/趁乱攻击豁免由会话层处理；
- 目标选择：ctx.extra["asset_card_ids"] 指定卡 id 列表；缺省自动选择
  手牌中打印费用最高的[seeker]支援卡（lv2：费用最高的前2张）；
- 放置入场复刻 _play_asset 流程（不支付所选卡费用）；引擎缺口：卡牌
  代码访问不到 CardRegistry，入场支援的实现无法即时注册（与偶遇一致）。
"""

from backend.cards.base import on_event
from backend.cards.seeker._selftest import CardSelfTest
from backend.models.enums import (
    CardType, GameEvent, PlayerClass, Skill, TimingPriority,
)
from backend.models.state import CardInstance


class UnearthTheAncients(CardSelfTest):
    card_id = "unearth_the_ancients_lv0"
    max_assets = 1  # lv2 覆盖为 2

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def investigate_for_assets(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        chosen = self._choose_assets(ctx, inv)
        if not chosen:
            ctx.extra["unearth_the_ancients_failed"] = "no_asset"
            return

        difficulty = sum(
            (ctx.game_state.get_card_data(c).cost or 0)
            if ctx.game_state.get_card_data(c) is not None else 0
            for c in chosen
        )
        result = self.run_self_test(
            ctx.game_state, inv.investigator_id, Skill.INTELLECT,
            difficulty, source=self.instance_id,
        )
        if result is None:
            ctx.extra["unearth_the_ancients_failed"] = "no_engine"
            return
        success, _margin = result
        if not success:
            ctx.extra["unearth_the_ancients_success"] = False
            ctx.game_state.log_effect("⛏️ 发掘古物：检定失败")
            return

        relics = 0
        played = []
        for card_id in chosen:
            cd = ctx.game_state.get_card_data(card_id)
            if cd is None or card_id not in inv.hand:
                continue
            inv.hand.remove(card_id)
            instance_id = ctx.game_state.next_instance_id()
            inst = CardInstance(
                instance_id=instance_id,
                card_id=card_id,
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
            played.append((card_id, instance_id))
            if "relic" in (cd.traits or []):
                relics += 1

        bus = getattr(self, "_bus", None)
        if bus is not None:
            from backend.engine.event_bus import EventContext
            for card_id, instance_id in played:
                bus.emit(EventContext(
                    game_state=ctx.game_state,
                    event=GameEvent.CARD_ENTERS_PLAY,
                    investigator_id=inv.investigator_id,
                    target=instance_id,
                    extra={"card_id": card_id},
                ))

        for _ in range(relics):
            if inv.deck:
                inv.hand.append(inv.deck.pop(0))

        ctx.extra["unearth_the_ancients_success"] = True
        ctx.extra["unearth_the_ancients_played"] = [c for c, _ in played]
        ctx.extra["unearth_the_ancients_relics"] = relics
        names = "、".join(ctx.game_state.card_name(c) for c, _ in played)
        ctx.game_state.log_effect(
            f"⛏️ 发掘古物：检定成功，【{names}】放置入场"
            + (f"，{relics}张遗物抽{relics}张牌" if relics else ""))

    def _choose_assets(self, ctx, inv) -> list[str]:
        """extra 指定或自动取手牌中费用最高的 seeker 支援（最多 max_assets）。"""
        wanted = ctx.extra.get("asset_card_ids")
        if wanted is None and ctx.extra.get("asset_card_id"):
            wanted = [ctx.extra["asset_card_id"]]
        if wanted is not None:
            return [
                c for c in list(wanted)[: self.max_assets]
                if c in inv.hand and self._is_seeker_asset(ctx, c)
            ]
        candidates = []
        for card_id in inv.hand:
            cd = ctx.game_state.get_card_data(card_id)
            if self._is_seeker_asset(ctx, card_id):
                candidates.append((cd.cost or 0, card_id))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [c for _, c in candidates[: self.max_assets]]

    @staticmethod
    def _is_seeker_asset(ctx, card_id) -> bool:
        cd = ctx.game_state.get_card_data(card_id)
        return (
            cd is not None
            and cd.type == CardType.ASSET
            and cd.card_class == PlayerClass.SEEKER
        )
