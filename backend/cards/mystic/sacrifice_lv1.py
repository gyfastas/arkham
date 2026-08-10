"""Sacrifice (Level 1) — Mystic Event. (Ritual)
弃掉你控制的1张[mystic]支援卡。然后，抽3张牌或获得3点资源，或两者的
任意组合。

简化说明：
- 弃哪张无选择 UI：默认弃你控制的第一张 mystic 支援卡；可在 CARD_PLAYED 的
  ctx.extra["discard_instance_id"] 指定。
- 抽牌/资源组合经 ctx.extra["draw_count"]（0-3，默认0=获得3资源）指定。
- 弃置为手动移除（ASSET_DEFEATED/CARD_LEAVES_PLAY 不补发——卡牌代码拿不到
  事件总线，同 astral_travel 惯例）；抽牌不触发 CARD_DRAWN 钩子（引擎缺口，
  同 quantum_flux）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, PlayerClass, TimingPriority


class Sacrifice(CardImplementation):
    card_id = "sacrifice_lv1"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        # 选择弃掉的 mystic 支援
        target_iid = ctx.extra.get("discard_instance_id")
        if target_iid is None or target_iid not in inv.play_area:
            target_iid = None
            for iid in inv.play_area:
                ci = ctx.game_state.get_card_instance(iid)
                if ci is None:
                    continue
                cd = ctx.game_state.get_card_data(ci.card_id)
                if cd is not None and cd.card_class == PlayerClass.MYSTIC:
                    target_iid = iid
                    break
        if target_iid is None:
            return  # 没有可弃的 mystic 支援：效果不发动

        ci = ctx.game_state.get_card_instance(target_iid)
        vacate_asset_slots(ctx.game_state, target_iid)
        inv.play_area.remove(target_iid)
        inv.discard.append(ci.card_id)
        ctx.game_state.cards_in_play.pop(target_iid, None)
        ctx.extra["sacrifice_discarded"] = ci.card_id

        # 抽3/资源3的任意组合
        draw_count = max(0, min(3, int(ctx.extra.get("draw_count", 0) or 0)))
        for _ in range(draw_count):
            if not inv.deck:
                break
            inv.hand.append(inv.deck.pop(0))
        inv.resources += 3 - draw_count
        ctx.extra["sacrifice_drawn"] = draw_count
        ctx.extra["sacrifice_resources"] = 3 - draw_count
