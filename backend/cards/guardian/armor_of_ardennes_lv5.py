"""Armor of Ardennes (Level 5) — Guardian Asset, Body slot. (03305)
生命4。
[反应]当伤害被分配给阿登护甲时，横置阿登护甲：取消其中1点伤害。

简化说明：
- 引擎在发出 DAMAGE_ASSIGNED 前已完成盟友/资产分担，事件上下文不含分担
  目标；本卡仿照 guard_dog 的增量检测：比较本卡已受伤害的增量判断是否有
  伤害被分配给本卡，横置并取消1点（直接扣减本卡已受的伤害）。
- 直接伤害（direct，不经过分配）按官方规则不触发本反应。
- 边缘情况：若本卡被治愈（无事件可监听）后再次承伤，增量基准可能偏高，
  少触发一次取消；下一次 DAMAGE_ASSIGNED 会重新同步基准。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class ArmorOfArdennes(CardImplementation):
    card_id = "armor_of_ardennes_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._known_damage: int | None = None  # 上次事件时本卡已受伤害

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.AFTER)
    def cancel_one_damage(self, ctx):
        """有伤害分配给本卡且本卡未横置：横置，取消其中1点。"""
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        previous = self._known_damage if self._known_damage is not None else 0
        if inst.damage > previous and not inst.exhausted:
            inst.exhausted = True
            inst.damage -= 1
            ctx.extra["armor_of_ardennes_cancelled"] = 1
            ctx.game_state.log_effect("🛡️ 阿登护甲：横置，取消分配给它的1点伤害")
        self._known_damage = inst.damage
