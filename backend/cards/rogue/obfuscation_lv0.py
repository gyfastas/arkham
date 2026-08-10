"""Obfuscation (Level 0) — Rogue Asset, Fast. (07027)
快速。使用(3充能)。
[反应]当敌人对你进行趁乱攻击时，花费1充能：取消该次攻击。

简化说明：
- 反应自动触发（官方为玩家选择；取消严格有利）：趁乱攻击事件
  （ATTACK_OF_OPPORTUNITY 可取消）时若本卡在场且有充能，自动花费1充能
  并取消。
- 数据 uses 键兼容双 s 写法（"chargess"）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def _uses_key(inst, key: str) -> str:
    """兼容源数据复数化笔误（"chargess"）。"""
    if key in inst.uses:
        return key
    alt = f"{key}s"
    return alt if alt in inst.uses else key


class Obfuscation(CardImplementation):
    card_id = "obfuscation_lv0"

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = _uses_key(inst, "charges")
        if inst.uses.get(key, 0) < 1:
            return
        inst.uses[key] -= 1
        ctx.cancel()
        ctx.extra["obfuscation_cancelled"] = True
        ctx.game_state.log_effect("🌫 隐惑术：花费1充能，取消趁乱攻击")
