"""Nephthys (Level 4) — Guardian Asset, Ally slot. (07262)
你获得+1[意志]。
[反应] 当1个或多个[祝福]标记在技能检定中将要从混乱袋被移除时：
改为将它们封印在纳芙蒂斯上。
[快速]横置纳芙蒂斯：释放封印在她上的3个[祝福]标记，或将封印在她上的
3个[祝福]标记返回供应堆，以对你所在地点的一个敌人造成2点伤害。

简化说明：
- 引擎抽标记不从袋中移除（draw 只读取），"祝福标记将被移除"在引擎中
  不发生（引擎缺口）。近似实现：技能检定中结算到[祝福]标记时，
  自动将其从袋中封印到纳芙蒂斯上（官方为检定结束后才离袋，时机提前、
  效果等价；多个祝福依次处理）。
- [快速]为公开方法 activate(mode=...)：mode="release" 释放3个封印祝福
  回混乱袋；mode="damage" 将3个封印祝福返回供应堆并对同地点一个敌人
  造成2点伤害（目标自动取同地点第一个敌人，可传 enemy_instance_id）。
- 封印数记录在实例 uses["sealed"]；混沌袋经 bind_chaos_bag() 注入。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_SEAL_COST = 3


class Nephthys(CardImplementation):
    card_id = "nephthys_lv4"
    activations = [{
        "id": "exhaust",
        "label": "[快速] 横置：释放3封印祝福，或返还3封印祝福对敌人造成2伤害",
        "method": "activate",
        "actions": 0,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """+1 意志（在场时）。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "nephthys_willpower_bonus")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.AFTER)
    def seal_bless(self, ctx):
        """检定中结算到祝福标记：改为封印在纳芙蒂斯上（近似，见 docstring）。"""
        if ctx.chaos_token != ChaosTokenType.BLESS or self._bag is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        owner = ctx.game_state.get_investigator(inst.controller_id)
        if owner is None or self.instance_id not in owner.play_area:
            return
        if self._bag.seal_token(ChaosTokenType.BLESS):
            inst.uses["sealed"] = inst.uses.get("sealed", 0) + 1
            ctx.extra["nephthys_sealed"] = inst.uses["sealed"]
            ctx.game_state.log_effect(
                f"👸 纳芙蒂斯：祝福标记改为封印在她上（现有{inst.uses['sealed']}个）")

    def activate(self, game_state, investigator_id: str, mode: str = "release",
                 enemy_instance_id: str | None = None) -> bool:
        """[快速] 横置：释放3封印祝福（release）或返还3个并对敌人造成2伤害（damage）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted or inst.uses.get("sealed", 0) < _SEAL_COST:
            return False

        inst.exhausted = True
        inst.uses["sealed"] -= _SEAL_COST

        if mode == "damage":
            # 3个封印祝福返回供应堆（不再回袋）
            if self._bag is not None:
                for _ in range(_SEAL_COST):
                    try:
                        self._bag.sealed.remove(ChaosTokenType.BLESS)
                    except ValueError:
                        break
            target_iid = enemy_instance_id or self._first_enemy_at(
                game_state, inv.location_id)
            if target_iid is not None:
                target = game_state.get_card_instance(target_iid)
                target_name = (
                    game_state.card_name(target.card_id) if target is not None
                    else target_iid
                )
                deal_damage_to_enemy(
                    game_state, self._bus, target_iid, 2,
                    defeated_by=investigator_id,
                )
                game_state.log_effect(
                    f"👸 纳芙蒂斯：返还3个祝福，对【{target_name}】造成2点伤害")
            else:
                game_state.log_effect("👸 纳芙蒂斯：返还3个祝福（同地点无敌人）")
            return True

        # release：3个封印祝福释放回混乱袋
        if self._bag is not None:
            for _ in range(_SEAL_COST):
                if not self._bag.release_token(ChaosTokenType.BLESS):
                    break
        game_state.log_effect("👸 纳芙蒂斯：释放3个封印的祝福回混乱袋")
        return True

    @staticmethod
    def _first_enemy_at(game_state, location_id) -> str | None:
        for other in game_state.get_investigators_at_location(location_id):
            if other.threat_area:
                return other.threat_area[0]
        loc = game_state.get_location(location_id)
        if loc is not None and loc.enemies:
            return loc.enemies[0]
        return None
