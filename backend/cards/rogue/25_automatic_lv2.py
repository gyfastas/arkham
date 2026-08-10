""".25 Automatic (Level 2) — Rogue Asset, Hand slot. (07305)
快速。使用(4子弹)。
[行动]花费1子弹：攻击。如果攻击的敌人已横置，这次攻击你+2战斗并造成+1伤害。
[反应]在你躲避你所在地点的敌人后：执行上述攻击能力，无须花费一个行动。

简化说明：
- 反应攻击简化为自动触发（官方为玩家选择时机）：你躲避你所在地点的
  敌人后，若本卡还有子弹，自动花费1子弹对该敌人（已横置，+2战斗/+1伤害
  生效）执行一次攻击。
- 卡牌事件处理器只持有 game_state，无法访问 game.skill_test_engine；
  反应攻击改用本地构建的 SkillTestEngine（无 registry，该次攻击不能投入
  卡牌——简化注明），命中伤害经 _shared.deal_damage_to_enemy 结算。
- 混沌袋经 bind_chaos_bag 注入（registry.activate_card 已接线；未注入时
  反应不触发）。
"""

import importlib

from backend.cards.base import on_event
from backend.cards._shared import deal_damage_to_enemy
from backend.models.enums import GameEvent, Skill, TimingPriority

_lv0 = importlib.import_module("backend.cards.rogue.25_automatic_lv0")
TwentyFiveAutomaticLv0 = _lv0.TwentyFiveAutomaticLv0


class TwentyFiveAutomaticLv2(TwentyFiveAutomaticLv0):
    card_id = "25_automatic_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.ENEMY_EVADED, priority=TimingPriority.REACTION)
    def free_fight_after_evade(self, ctx):
        """[反应]躲避你所在地点的敌人后：免费执行一次攻击（仍花费1子弹）。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        enemy_id = ctx.enemy_id
        if not enemy_id:
            return
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is None or enemy_id not in loc.enemies:
            return  # 仅对你所在地点的敌人（躲避后敌人回到该地点）
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or card.uses.get("ammo", 0) < 1:
            return
        enemy = ctx.game_state.get_card_instance(enemy_id)
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None:
            return
        if self._bus is None or self._chaos_bag is None:
            return

        # 花费1子弹并立即攻击（不花费行动）；目标已横置 → +2战斗/+1伤害
        card.uses["ammo"] -= 1
        self._attack_paid = True
        self._target_exhausted = True
        ctx.extra["25_automatic_lv2_free_fight"] = enemy_id
        ctx.game_state.log_effect(
            f"🔫 .25自动手枪(2级)：躲避后免费攻击【{ctx.game_state.card_name(enemy.card_id)}】")

        from backend.engine.skill_test import SkillTestEngine
        engine = SkillTestEngine(ctx.game_state, self._bus, self._chaos_bag)

        def on_success(result):
            bonus = int(result.extra.get("bonus_damage", 0) or 0)
            total = max(0, 1 + bonus)
            deal_damage_to_enemy(
                ctx.game_state, self._bus, enemy_id, total,
                defeated_by=inv.investigator_id,
            )

        engine.run_test(
            investigator_id=inv.investigator_id,
            skill_type=Skill.COMBAT,
            difficulty=enemy_data.enemy_fight or 0,
            source_instance_id=self.instance_id,
            on_success=on_success,
        )
        # 嵌套检定的 SKILL_TEST_ENDS 已清除攻击状态（source 匹配），兜底再清一次
        self._attack_paid = False
        self._target_exhausted = False
