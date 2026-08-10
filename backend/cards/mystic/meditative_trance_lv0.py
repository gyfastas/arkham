"""Meditative Trance (Level 0) — Mystic Event.
你的每个已占用的奥秘槽：治愈1点伤害或1点恐惧。

简化说明：
- 伤害/恐惧分配无选择 UI：默认先治愈伤害、余下治愈恐惧；
  可在 CARD_PLAYED 的 ctx.extra 传 heal_damage / heal_horror 指定分配。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, SlotType, TimingPriority


class MeditativeTrance(CardImplementation):
    card_id = "meditative_trance_lv0"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def heal(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        filled = 0
        for iid in inv.play_area:
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None:
                continue
            cd = ctx.game_state.get_card_data(ci.card_id)
            if cd is not None and SlotType.ARCANE in (cd.slots or []):
                filled += 1
        if filled <= 0:
            return

        heal_damage = ctx.extra.get("heal_damage")
        heal_horror = ctx.extra.get("heal_horror")
        if heal_damage is None and heal_horror is None:
            # 简化：默认先治愈伤害，余下治愈恐惧
            heal_damage = min(filled, inv.damage)
            heal_horror = filled - heal_damage
        heal_damage = min(int(heal_damage or 0), inv.damage)
        heal_horror = min(int(heal_horror or 0), inv.horror)
        inv.damage -= heal_damage
        inv.horror -= heal_horror
        ctx.extra["meditative_trance_healed_damage"] = heal_damage
        ctx.extra["meditative_trance_healed_horror"] = heal_horror
