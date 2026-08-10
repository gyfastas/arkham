"""Detective's Colt 1911s (Level 0) — Neutral Asset, Weapon (Joe Diamond deck only).
使用（4弹药）。
你控制的至多2张[[Tool]]支援不占用手槽。
[行动]花费1弹药：战斗。本次攻击+1[combat]，造成+1伤害。若本次攻击击败
1个敌人，你可以将1张[[Insight]]事件从你的弃牌堆移动到你的直觉牌组底。

简化说明：
- "花费1弹药"是攻击动作的费用（无论命中与否），同 jennys_twin_45s_lv0。
- "Tool支援不占手槽"：槽位计算在引擎 _play_asset 内，不咨询卡牌
  （引擎缺口），未接线。
- 直觉牌组（hunch deck）引擎无独立存储：以
  scenario.vars["hunch_deck_{investigator_id}"]（list，底=append）近似，
  击败触发时自动移动弃牌堆中第一张直觉事件（官方为"可以"，即可选）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, Skill, TimingPriority


class DetectivesColt1911s(CardImplementation):
    card_id = "detectives_colt_1911s_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attack_paid = False  # 本次攻击已付1弹药

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_on_attack(self, ctx):
        """Spend 1 ammo as the cost of attacking with this weapon."""
        self._attack_paid = False
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """+1 Combat for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(1, "detectives_colt_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        """+1 damage for the attack paid for with this weapon."""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        ctx.modify_amount(1, "detectives_colt_extra_damage")

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def recycle_insight(self, ctx):
        """本次攻击击败敌人：弃牌堆第一张直觉事件移到直觉牌组底。"""
        if not self._attack_paid:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or ctx.investigator_id != card.owner_id:
            return
        inv = ctx.game_state.get_investigator(card.owner_id)
        if inv is None:
            return
        for cid in list(inv.discard):
            cd = ctx.game_state.get_card_data(cid)
            if (
                cd is not None
                and cd.type == CardType.EVENT
                and "insight" in (cd.traits or [])
            ):
                inv.discard.remove(cid)
                hunch_deck = ctx.game_state.scenario.vars.setdefault(
                    f"hunch_deck_{inv.investigator_id}", [])
                hunch_deck.append(cid)  # 牌组底
                ctx.extra["detectives_colt_recycled"] = cid
                ctx.game_state.log_effect(
                    f"🔍 侦探柯尔特：【{ctx.game_state.card_name(cid)}】"
                    "移到直觉牌组底")
                break

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_flag(self, ctx):
        self._attack_paid = False
