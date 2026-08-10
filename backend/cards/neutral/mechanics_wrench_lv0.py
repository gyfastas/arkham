"""Mechanic's Wrench (Level 0) — Neutral Asset, Hand slot. Daniela Reyes 专属。
[fast] 横置机械师扳手：选择你所在地点的1名敌人。该敌人攻击你。
[action]：战斗。只能对自你上回合结束以来攻击过你的敌人使用。本次攻击
+2[combat]并造成+1伤害。

简化说明：
- [fast] 实现为 activate_provoke()：发出 ENEMY_ATTACKS（可被 Dodge 取消），
  未取消则按敌人数据结算伤害/恐惧；无论是否取消，该敌人都记入
  "攻击过你"集合（官方即使被取消也算攻击过——若严格按"攻击过你"语义，
  取消视为未攻击，此处按结算了伤害或尝试攻击均记录，注明偏差：
  实际按"攻击结算完成"记录，即被取消时不记录）。
- [action] 战斗走引擎常规 FIGHT 通道（weapon_instance_id=本卡）：
  目标不在"攻击过你"集合时取消攻击（FIGHT_ACTION_INITIATED 可取消）。
- "攻击过你"集合在你回合结束时清空。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.event_bus import EventContext
from backend.models.enums import GameEvent, Skill, TimingPriority


class MechanicsWrench(CardImplementation):
    card_id = "mechanics_wrench_lv0"
    activations = [
        {
            "id": "provoke",
            "label": "【快速】横置：选择同地点敌人攻击你",
            "method": "activate_provoke",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._attackers: set[str] = set()
        self._fight_armed = False

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def activate_provoke(self, game_state, investigator_id,
                         enemy_instance_id: str | None = None) -> bool:
        """[fast] 横置：选择你所在地点的1名敌人，它攻击你。"""
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(investigator_id)
        if inst is None or inv is None or inst.exhausted:
            return False
        enemy_iid = enemy_instance_id or self._pick_enemy(game_state, inv)
        enemy = game_state.get_card_instance(enemy_iid) if enemy_iid else None
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return False

        inst.exhausted = True
        attack_ctx = EventContext(
            game_state=game_state,
            event=GameEvent.ENEMY_ATTACKS,
            investigator_id=investigator_id,
            enemy_id=enemy_iid,
        )
        if self._bus is not None:
            self._bus.emit(attack_ctx)
        if attack_ctx.cancelled:
            game_state.log_effect("🔧 机械师扳手：敌人的攻击被取消")
            return True
        from backend.engine.damage import DamageEngine
        DamageEngine(game_state, self._bus).deal_damage(
            investigator_id,
            damage=enemy_data.enemy_damage or 0,
            horror=enemy_data.enemy_horror or 0,
            source=enemy_iid,
        )
        self._attackers.add(enemy_iid)
        game_state.log_effect("🔧 机械师扳手：敌人攻击你")
        return True

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.AFTER)
    def record_attacker(self, ctx):
        """记录自回合结束以来攻击过你的敌人（敌方阶段常规攻击）。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or ctx.cancelled:
            return
        if inst.controller_id != ctx.investigator_id:
            return
        if ctx.enemy_id:
            self._attackers.add(ctx.enemy_id)

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def gate_fight(self, ctx):
        """只能对攻击过你的敌人使用战斗能力。"""
        if ctx.source != self.instance_id:
            return
        self._fight_armed = False
        if ctx.enemy_id not in self._attackers:
            ctx.game_state.log_effect(
                "🔧 机械师扳手：目标自上回合结束以来未攻击过你，无法使用"
            )
            ctx.cancel()
            return
        self._fight_armed = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.source != self.instance_id or not self._fight_armed:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "mechanics_wrench_combat_bonus")

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def extra_damage(self, ctx):
        if ctx.source != self.instance_id or not self._fight_armed:
            return
        ctx.modify_amount(1, "mechanics_wrench_extra_damage")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_fight_flag(self, ctx):
        self._fight_armed = False

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def clear_attackers(self, ctx):
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.controller_id == ctx.investigator_id:
            self._attackers.clear()

    @staticmethod
    def _pick_enemy(game_state, inv):
        if inv.threat_area:
            return inv.threat_area[0]
        location = game_state.get_location(inv.location_id)
        if location is not None and location.enemies:
            return location.enemies[0]
        return None
