"""Gaze of Ouraxsh (Level 2) — Seeker Event. (07155)
从混乱袋随机揭示7个标记。对你所在地点的敌人造成总计为1+抽出的[curse]
和[auto_fail]标记数量的伤害（由你分配）。本行动不会引起趁乱攻击。

简化说明：
- 伤害分配默认全部给你所在地点的第一个敌人（交战优先）；可用
  ctx.extra["enemy_instance_id"] 指定单一目标，或 ctx.extra["damage_split"]
  （{enemy_instance_id: amount}）显式分配（官方为玩家自由分配）；
- 揭示的标记结算后放回混乱袋（官方规则；本引擎 ChaosBag.draw 不移出
  标记，天然等效）；袋中不足7个时揭示全部；
- 伤害经 _shared.deal_damage_to_enemy 结算（含击败处理）；
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）；
  未绑定时效果不发动；
- 不引起趁乱攻击：CARD_PLAYED 先于 AoO 发出，武装一次性豁免标记，
  取消随后的 ATTACK_OF_OPPORTUNITY（与 ill_see_you_in_hell 一致）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_BONUS_TOKENS = {ChaosTokenType.CURSE, ChaosTokenType.AUTO_FAIL}


class GazeOfOuraxsh(CardImplementation):
    card_id = "gaze_of_ouraxsh_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None
        self._aoo_free: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def reveal_tokens_and_damage(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._chaos_bag is None:
            return

        enemies = self._enemies_at(ctx, inv.location_id)
        if not enemies:
            return

        # 揭示7个标记（引擎 ChaosBag.draw 不移出标记，天然等效"揭示后放回"）
        drawn = []
        for _ in range(min(7, len(self._chaos_bag.tokens))):
            drawn.append(self._chaos_bag.draw())
        bonus = sum(1 for t in drawn if t in _BONUS_TOKENS)
        total = 1 + bonus
        ctx.extra["gaze_tokens"] = [t.value for t in drawn]
        ctx.extra["gaze_damage"] = total

        # 分配伤害（默认全部给第一个敌人）
        split = ctx.extra.get("damage_split")
        if not split:
            target = ctx.extra.get("enemy_instance_id") or enemies[0]
            split = {target: total}
        for enemy_iid, amount in split.items():
            if amount > 0 and enemy_iid in enemies:
                deal_damage_to_enemy(
                    ctx.game_state, self._bus, enemy_iid, amount,
                    defeated_by=inv.investigator_id,
                )
        ctx.game_state.log_effect(
            f"👁️ 乌拉赫什之凝视：揭示{len(drawn)}个标记"
            f"（{bonus}个诅咒/自动失败），造成共{total}点伤害"
        )

        # 本行动不引起趁乱攻击
        self._aoo_free = inv.investigator_id

    @staticmethod
    def _enemies_at(ctx, location_id: str) -> list[str]:
        """你所在地点的敌人：与你交战者优先，其后地点上未交战者。"""
        out: list[str] = []
        for inv in ctx.game_state.get_investigators_at_location(location_id):
            for eid in inv.threat_area:
                if eid in ctx.game_state.cards_in_play and eid not in out:
                    out.append(eid)
        loc = ctx.game_state.get_location(location_id)
        if loc is not None:
            for eid in loc.enemies:
                if eid in ctx.game_state.cards_in_play and eid not in out:
                    out.append(eid)
        return out

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        if self._aoo_free is not None and ctx.investigator_id == self._aoo_free:
            ctx.cancel()

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_aoo(self, ctx):
        self._aoo_free = None
