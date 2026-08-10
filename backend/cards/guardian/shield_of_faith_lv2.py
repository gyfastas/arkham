"""Shield of Faith (Level 2) — Guardian Asset, Arcane slot. (07221)
封印(最多5[bless])。如果信仰之盾上没有封印的标记，将其丢弃。
[reaction]在一名敌人攻击你所在地点的一位调查员时，消耗信仰之盾并释放一个
封印在此的混乱标记：取消该次攻击。

简化说明：
- 入场时自动从混乱袋封印至多5个祝福标记（官方为"最多"，自动取最大值）。
- 取消攻击为自动触发（官方为玩家选择时机）：敌人攻击持有者同地点的调查员
  时，若未横置且有封印标记，自动消耗并释放1个标记取消攻击（ENEMY_ATTACKS
  可取消，与 dodge 的自动豁免约定一致）。
- 释放最后一个封印标记后本卡丢弃（镜像引擎离场流程）。
"""

from backend.cards._shared import defeat_asset
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_MAX_SEAL = 5


class ShieldOfFaith(CardImplementation):
    card_id = "shield_of_faith_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None
        self._bus = None
        self._sealed = 0

    def bind_chaos_bag(self, bag) -> None:
        self._bag = bag

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_on_enter(self, ctx):
        """入场：从混乱袋封印至多5个祝福标记；一个没有则丢弃。"""
        if ctx.target != self.instance_id:
            return
        if self._bag is not None:
            while self._sealed < _MAX_SEAL and self._bag.seal_token(ChaosTokenType.BLESS):
                self._sealed += 1
        if self._sealed:
            ctx.game_state.log_effect(
                f"🛡️ 信仰之盾：封印{self._sealed}个祝福标记")
        else:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🛡️ 信仰之盾：没有封印的标记，丢弃")

    @on_event(GameEvent.ENEMY_ATTACKS, priority=TimingPriority.WHEN)
    def cancel_attack(self, ctx):
        """敌人攻击同地点调查员时：消耗并释放1个封印标记，取消该次攻击。"""
        holder = self._holder(ctx.game_state)
        if holder is None:
            return
        target = ctx.game_state.get_investigator(ctx.investigator_id)
        if target is None or target.location_id != holder.location_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or self._sealed <= 0:
            return

        inst.exhausted = True
        self._sealed -= 1
        if self._bag is not None:
            self._bag.release_token(ChaosTokenType.BLESS)
        ctx.cancel()
        ctx.game_state.log_effect("🛡️ 信仰之盾：消耗并释放1个封印标记，取消敌人攻击")

        if self._sealed <= 0:
            defeat_asset(ctx.game_state, self._bus, self.instance_id)
            ctx.game_state.log_effect("🛡️ 信仰之盾：没有封印的标记，丢弃")

    def _holder(self, game_state):
        for inv in game_state.investigators.values():
            if self.instance_id in inv.play_area:
                return inv
        return None
