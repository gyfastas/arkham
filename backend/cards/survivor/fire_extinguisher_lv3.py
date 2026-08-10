"""Fire Extinguisher (Level 3) — Survivor Asset, Hand slot.
[行动]：攻击。本次攻击+1[战斗]并造成+1伤害。
[行动] 丢弃灭火器：躲避。自动躲避所有与你交战的敌人。你可以改为放逐
灭火器来丢弃每名被此效果躲避的非[[精英]]敌人。

简化说明：
- 攻击为以本武器发起的战斗（ctx.source 为本卡实例）：+1战斗、成功时
  +1伤害（bonus_damage 通道）。
- 躲避为公开方法 activate_evade()（activations 已声明，1行动）：自动躲避
  所有交战敌人（横置+脱离+留在地点，补发 ENEMY_EVADED）；exile=True 时
  灭火器放逐（exiled_cards，引擎无放逐区）且每名被躲避的非精英敌人
  被丢弃（进遭遇弃牌堆）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class FireExtinguisher(CardImplementation):
    card_id = "fire_extinguisher_lv3"
    activations = [
        {"id": "fight", "label": "[行动] 攻击：+1战斗、+1伤害",
         "method": "noop_fight", "actions": 1, "target": "enemy"},
        {"id": "evade", "label": "[行动] 丢弃灭火器：自动躲避所有交战敌人",
         "method": "activate_evade", "actions": 1},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def noop_fight(self, game_state, investigator_id: str) -> bool:
        """攻击经会话层战斗行动发起（weapon_instance_id=本卡实例）。"""
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """以本卡攻击时 +1 战斗。"""
        if ctx.source != self.instance_id or ctx.skill_type != Skill.COMBAT:
            return
        ctx.modify_amount(1, "fire_extinguisher_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """以本卡攻击成功时 +1 伤害。"""
        if ctx.source != self.instance_id or ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

    def activate_evade(self, game_state, investigator_id: str,
                       exile: bool = False) -> bool:
        """[行动] 丢弃（或放逐）灭火器：自动躲避所有与你交战的敌人。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        loc = game_state.get_location(inv.location_id)

        engaged = list(inv.threat_area)
        evaded = []
        for enemy_iid in engaged:
            enemy = game_state.get_card_instance(enemy_iid)
            if enemy is None:
                continue
            enemy.exhausted = True
            inv.threat_area.remove(enemy_iid)
            if loc is not None and enemy_iid not in loc.enemies:
                loc.enemies.append(enemy_iid)
            evaded.append(enemy_iid)
            if self._bus is not None:
                from backend.engine.event_bus import EventContext
                self._bus.emit(EventContext(
                    game_state=game_state,
                    event=GameEvent.ENEMY_EVADED,
                    investigator_id=investigator_id,
                    enemy_id=enemy_iid,
                ))

        # 放逐模式：丢弃每名被躲避的非精英敌人
        discarded = []
        if exile:
            for enemy_iid in evaded:
                enemy = game_state.get_card_instance(enemy_iid)
                if enemy is None:
                    continue
                enemy_cd = game_state.get_card_data(enemy.card_id)
                if enemy_cd is not None and is_elite_enemy(enemy_cd):
                    continue
                if loc is not None and enemy_iid in loc.enemies:
                    loc.enemies.remove(enemy_iid)
                game_state.cards_in_play.pop(enemy_iid, None)
                game_state.scenario.encounter_discard.append(enemy.card_id)
                discarded.append(enemy.card_id)

        # 丢弃/放逐灭火器本体
        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        if exile:
            game_state.scenario.vars.setdefault(
                "exiled_cards", []).append(self.card_id)
        else:
            inv.discard.append(self.card_id)

        game_state.log_effect(
            f"🧯 灭火器：自动躲避{len(evaded)}名敌人"
            + (f"，丢弃非精英敌人{len(discarded)}名并放逐灭火器" if exile else ""))
        return True
