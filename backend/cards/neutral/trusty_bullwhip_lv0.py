"""Trusty Bullwhip (Level 0) — Neutral Asset, Hand slot. 蒙特尼·杰克专属。
快速。
[行动]：战斗。本次攻击使用敏捷代替战斗。如果本次攻击成功，你可以横置
可靠的长鞭，选择自动躲避被攻击的敌人，或让本次攻击造成+1伤害。

简化说明：
- activate(on_success=...) 武装一次攻击，随后由会话层发起战斗行动
  （weapon_instance_id 传本卡实例）；敏捷代替战斗经 SKILL_VALUE_DETERMINED
  换技实现（同 shrivelling_lv0 的意志换战斗）。
- 卡面"成功后选择"在引擎中没有成功判定与伤害结算之间的选择窗口，简化为
  激活时预选（on_success="damage" 默认 +1伤害 / "evade" 自动躲避）；成功
  且长鞭未横置时才生效（横置为代价，官方为可选，已横置即视为不发动）。
- 自动躲避镜像 ActionResolver._evade 的成功结算：横置敌人、脱离交战、
  放置到持有者地点并发出 ENEMY_EVADED。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TrustyBullwhip(CardImplementation):
    card_id = "trusty_bullwhip_lv0"
    activations = [{
        "id": "fight",
        "label": "[行动]用敏捷战斗；成功时可横置长鞭：+1伤害或自动躲避",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._armed = False
        self._on_success = "damage"  # "damage" | "evade"（激活时预选）
        self._target_enemy = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def activate(self, game_state, investigator_id: str,
                 on_success: str = "damage") -> bool:
        """[行动]武装一次"用敏捷战斗"；on_success 预选成功后的横置效果。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if on_success not in ("damage", "evade"):
            return False
        self._armed = True
        self._on_success = on_success
        self._target_enemy = None
        return True

    def _is_this_attack(self, ctx) -> bool:
        return self._armed and ctx.source == self.instance_id

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def record_target(self, ctx):
        if ctx.source == self.instance_id:
            self._target_enemy = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_agility(self, ctx):
        """本次攻击使用敏捷代替战斗。"""
        if ctx.skill_type != Skill.COMBAT or not self._is_this_attack(ctx):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        base_val = inv.get_skill(ctx.skill_type)
        agility = inv.get_skill(Skill.AGILITY)
        ctx.modify_amount(agility - base_val, "bullwhip_substitute_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def success_effect(self, ctx):
        """攻击成功：横置长鞭，+1伤害或自动躲避被攻击的敌人。"""
        if not self._is_this_attack(ctx):
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return  # 已横置即不发动（官方为可选效果）
        inst.exhausted = True
        if self._on_success == "damage":
            ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 1
        else:
            self._auto_evade(ctx)

    def _auto_evade(self, ctx) -> None:
        """自动躲避被攻击的敌人（镜像 ActionResolver._evade 成功结算）。"""
        enemy_id = self._target_enemy
        enemy = ctx.game_state.get_card_instance(enemy_id) if enemy_id else None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if enemy is None or inv is None:
            return
        enemy.exhausted = True
        if enemy_id in inv.threat_area:
            inv.threat_area.remove(enemy_id)
        location = ctx.game_state.get_location(inv.location_id)
        if location is not None and enemy_id not in location.enemies:
            location.enemies.append(enemy_id)
        ctx.game_state.log_effect("🪢 可靠的长鞭：自动躲避被攻击的敌人")
        if self._bus is not None:
            from backend.engine.event_bus import EventContext
            self._bus.emit(EventContext(
                game_state=ctx.game_state,
                event=GameEvent.ENEMY_EVADED,
                investigator_id=ctx.investigator_id,
                enemy_id=enemy_id,
            ))

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._target_enemy = None
