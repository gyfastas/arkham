""".45 Thompson (Level 3) — Rogue Asset, Hand x2 slot. (05187)
使用(5子弹)。
[行动]花费1子弹：攻击。你这次攻击+2战斗并造成+1伤害。如果你成功且超过
难度至少X点，你可以花费1子弹来对你所在地点的另一名敌人造成这次攻击的
伤害，X为该敌人的攻击值。

简化说明：
- 子弹在发起攻击时（FIGHT_ACTION_INITIATED）扣除，无子弹时取消攻击
  （lupara 同模式）。
- 溅射目标自动选择你所在地点第一个"攻击值 ≤ 超出值"的其他敌人
  （官方为玩家自选；可经 ctx.extra["thompson_spread_target"] 指定）。
- "可以花费1子弹"简化为有子弹即自动花费并结算溅射（有利分支）。
- 溅射伤害 = 本次攻击总伤害（基础1 + bonus_damage 全部加成），经
  _shared.deal_damage_to_enemy 直接结算（不走 DAMAGE_DEALT 修改窗口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import GameEvent, Skill, TimingPriority


class FortyFiveThompsonLv3(CardImplementation):
    card_id = "45_thompson_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attack_paid = False
        self._target_id: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """花费1子弹：攻击。无子弹时攻击被取消（不花费行动）。"""
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            self._attack_paid = False
            self._target_id = None
            ctx.cancel()
            ctx.game_state.log_effect("🔫 .45汤姆逊冲锋枪：没有子弹，攻击取消")
            return
        card.uses["ammo"] -= 1
        self._attack_paid = True
        self._target_id = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击+2战斗。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "45_thompson_combat_bonus")

    def _enemies_at_location(self, ctx, inv) -> list[str]:
        """你所在地点的敌人（未交战 + 与任何调查员交战的）。"""
        out: list[str] = []
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None:
            out.extend(loc.enemies)
        for other in ctx.game_state.investigators.values():
            if other.location_id != inv.location_id:
                continue
            for eid in other.threat_area:
                if eid not in out:
                    out.append(eid)
        return out

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def bonus_damage_and_spread(self, ctx):
        """+1伤害；成功且超出难度至少X点：花1子弹对另一敌人造成同等伤害。"""
        if ctx.source != self.instance_id or not self._attack_paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) < 1:
            return

        # 选择溅射目标：你所在地点攻击值 ≤ 超出值的另一名敌人
        target_id = ctx.extra.get("thompson_spread_target")
        candidates = [
            eid for eid in self._enemies_at_location(ctx, inv)
            if eid != self._target_id
        ]
        chosen = None
        for eid in candidates:
            enemy = ctx.game_state.get_card_instance(eid)
            edata = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
            if edata is None:
                continue
            if target_id is not None and eid != target_id:
                continue
            if (edata.enemy_fight or 0) > margin:
                continue
            chosen = eid
            break
        if chosen is None:
            return

        card.uses["ammo"] -= 1
        total = max(0, 1 + int(ctx.extra.get("bonus_damage", 0) or 0))
        deal_damage_to_enemy(
            ctx.game_state, self._bus, chosen, total,
            defeated_by=inv.investigator_id,
        )
        ctx.extra["thompson_spread"] = {"enemy_id": chosen, "damage": total}
        enemy = ctx.game_state.get_card_instance(chosen)
        name = ctx.game_state.card_name(enemy.card_id) if enemy else chosen
        ctx.game_state.log_effect(
            f"🔫 .45汤姆逊冲锋枪：超出{margin}点，花1子弹对【{name}】造成{total}点伤害")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_attack_state(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_paid = False
            self._target_id = None
