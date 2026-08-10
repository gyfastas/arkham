"""St. Hubert's Key (Level 0) — Mystic Asset, Accessory slot. (03269)
你获得+1[willpower]、+1[intellect]，并-2神智值。
[reaction] 在你将要因恐惧被击败时，丢弃圣胡伯的钥匙：立即治愈2点恐惧。

简化说明：
- -2神智值经 sanity_bonus 实现（入场-2、离场+2）。
- 救命反应：INVESTIGATOR_DEFEATED 时若恐惧达到神智上限（即因恐惧被击败），
  自动丢弃本卡并治愈2恐惧；弃牌后-2神智移除，实际等效多出4点余量。
  伤害与恐惧同时达标时按恐惧击败处理（官方为玩家选择，简化取有利分支）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class StHubertsKey(CardImplementation):
    card_id = "st_huberts_key_lv0"

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def skill_bonus(self, ctx):
        """+1意志、+1智力。"""
        if ctx.skill_type not in (Skill.WILLPOWER, Skill.INTELLECT):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "st_huberts_key_bonus")

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def enter_play(self, ctx):
        """入场：-2神智值。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.sanity_bonus -= 2

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def leaves_play(self, ctx):
        """离场：恢复-2神智值。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.sanity_bonus += 2

    @on_event(GameEvent.INVESTIGATOR_DEFEATED, priority=TimingPriority.WHEN)
    def save_from_horror_defeat(self, ctx):
        """因恐惧被击败时：丢弃本卡，立即治愈2恐惧。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if inv.horror < inv.sanity:
            return  # 非恐惧击败

        inst = ctx.game_state.get_card_instance(self.instance_id)
        card_id = inst.card_id if inst is not None else self.card_id

        # 丢弃本卡（先离场恢复神智上限，再治愈恐惧）
        vacate_asset_slots(ctx.game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        inv.discard.append(card_id)
        ctx.game_state.cards_in_play.pop(self.instance_id, None)
        inv.sanity_bonus += 2  # 恢复-2神智（无总线补发 CARD_LEAVES_PLAY，手动还原）

        inv.horror = max(0, inv.horror - 2)
        ctx.extra["st_huberts_key_saved"] = True
        ctx.game_state.log_effect("🗝️ 圣胡伯的钥匙：丢弃并治愈2恐惧，免于被击败")
