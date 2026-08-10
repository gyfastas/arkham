"""Flamethrower (Level 5) — Guardian Asset, Body + Hand x2. (04305)
使用(4弹药)。
[行动]花费1弹药：攻击。本次攻击的目标必须是你交战的敌人中战斗值最高者。
本次攻击你获得+4战斗。如果本次攻击成功，不造成标准伤害，改为在你交战的
敌人之间分配至多4点伤害（任何额外伤害加在此总数上）。

简化说明：
- 弹药在 FIGHT_ACTION_INITIATED（以本武器发起攻击）时扣除（未命中同样消耗，
  同 rolands_38_special）；0弹药时攻击被取消（本能力以弹药为费用）。
- "必须选择交战敌人中战斗值最高者"：发起攻击时若目标不属于最高战斗值一档
  则取消攻击（并列最高时任选其一均合法）。
- 伤害分配自动选择：先给被攻击的敌人（至多填满其剩余生命），再按威胁区顺序
  分配给其他交战敌人（各至多填满剩余生命），剩余全数堆给被攻击的敌人
  （官方为玩家自由分配"至多"4点，可经 ctx.extra["flamethrower_assignment"]
  = {enemy_instance_id: amount} 指定分配，总额为4+额外伤害）。
- 其他+伤害效果（如致命打击）加在4点总数上，随被攻击敌人的份额一并结算。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_BASE_DAMAGE = 4


class Flamethrower(CardImplementation):
    card_id = "flamethrower_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._paid = False
        self._target: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_ammo_and_check_target(self, ctx):
        """扣1弹药；目标必须是交战敌人中战斗值最高者之一。"""
        self._paid = False
        self._target = None
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("🔥 火焰喷射器：没有弹药，无法攻击")
            return
        engaged = ctx.game_state.get_engaged_enemies(ctx.investigator_id)
        if not engaged:
            ctx.cancel()
            return
        fight_values = [
            (ctx.game_state.get_card_data(e.card_id).enemy_fight or 0)
            for e in engaged
            if ctx.game_state.get_card_data(e.card_id) is not None
        ]
        if not fight_values:
            ctx.cancel()
            return
        max_fight = max(fight_values)
        target = ctx.game_state.get_card_instance(ctx.enemy_id)
        target_data = (
            ctx.game_state.get_card_data(target.card_id) if target else None
        )
        if (
            target is None
            or target.instance_id not in {e.instance_id for e in engaged}
            or target_data is None
            or (target_data.enemy_fight or 0) < max_fight
        ):
            ctx.cancel()
            ctx.game_state.log_effect(
                "🔥 火焰喷射器：目标必须是交战敌人中战斗值最高者")
            return
        card.uses["ammo"] -= 1
        self._paid = True
        self._target = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击 +4 战斗。"""
        if ctx.source != self.instance_id or not self._paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(4, "flamethrower_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def distribute_damage(self, ctx):
        """成功：标准伤害替换为4点，在交战敌人之间分配。"""
        if ctx.source != self.instance_id or not self._paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = int(ctx.extra.get("bonus_damage", 0) or 0)
        total = _BASE_DAMAGE + bonus

        engaged = ctx.game_state.get_engaged_enemies(ctx.investigator_id)
        target_iid = self._target
        assignment = ctx.extra.get("flamethrower_assignment")
        if not assignment:
            # 自动分配：先填满被攻击敌人，再按威胁区顺序填满其他交战敌人
            assignment = {}
            remaining = total
            attacked = next(
                (e for e in engaged if e.instance_id == target_iid), None
            )
            order = [e for e in engaged if e is not attacked]
            if attacked is not None:
                order.insert(0, attacked)
            last = None
            for enemy in order:
                if remaining <= 0:
                    break
                data = ctx.game_state.get_card_data(enemy.card_id)
                hp = (data.enemy_health or 0) - enemy.damage if data else 0
                share = min(remaining, max(hp, 0))
                if share > 0:
                    assignment[enemy.instance_id] = share
                    remaining -= share
                    last = enemy.instance_id
            if remaining > 0:
                # 溢出伤害堆给被攻击的敌人（过量击杀）
                dump = target_iid or last
                if dump is not None:
                    assignment[dump] = assignment.get(dump, 0) + remaining

        attacked_iid = target_iid or next(iter(assignment), None)
        attacked_share = assignment.get(attacked_iid, 0)
        # 被攻击敌人的份额经引擎标准通道结算（bonus_damage = 份额-1）
        ctx.extra["bonus_damage"] = max(attacked_share - 1, -1)
        ctx.extra["flamethrower_assignment"] = dict(assignment)

        # 其他交战敌人的份额直接结算（含击败流程）
        for enemy_iid, amount in assignment.items():
            if enemy_iid == attacked_iid or amount <= 0:
                continue
            deal_damage_to_enemy(
                ctx.game_state, self._bus, enemy_iid, amount,
                defeated_by=ctx.investigator_id,
            )
        ctx.game_state.log_effect(
            f"🔥 火焰喷射器：在交战敌人间分配{total}点伤害 {assignment}")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._paid = False
        self._target = None
