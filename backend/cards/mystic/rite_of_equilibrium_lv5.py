"""Rite of Equilibrium (Level 5) — Mystic Event. (Blessed/Cursed)
二选一：
- 向混乱袋加入X个[curse]标记，以加入X个[bless]标记。
- 从混乱袋移除X个[curse]和X个[bless]标记，以治愈你所在地点卡牌上的共X点恐惧。

简化说明：
- 两种模式经公开方法 exchange() / remove_and_heal() 调用；CARD_PLAYED 时按
  ctx.extra["mode"]（"exchange"/"heal"，默认 "exchange"）与 ctx.extra["x"]
  （默认1）分派。
- 祝福/诅咒标记遵守官方上限：袋中（含封印区）各不超过10个。
- 治愈恐惧无选择 UI：自动从同地点恐惧最多的调查员开始依次治愈。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

MAX_TOKENS_PER_KIND = 10


class RiteOfEquilibrium(CardImplementation):
    card_id = "rite_of_equilibrium_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    def _count(self, token) -> int:
        bag = self._chaos_bag
        if bag is None:
            return 0
        return sum(1 for t in bag.tokens + bag.sealed if t == token)

    def exchange(self, game_state, x: int = 1) -> int:
        """加入X个[curse]以加入X个[bless]。返回实际加入的对数。"""
        bag = self._chaos_bag
        if bag is None or x <= 0:
            return 0
        room = min(
            MAX_TOKENS_PER_KIND - self._count(ChaosTokenType.CURSE),
            MAX_TOKENS_PER_KIND - self._count(ChaosTokenType.BLESS),
        )
        n = min(int(x), max(0, room))
        for _ in range(n):
            bag.add_token(ChaosTokenType.CURSE)
            bag.add_token(ChaosTokenType.BLESS)
        return n

    def remove_and_heal(self, game_state, investigator_id: str, x: int = 1) -> int:
        """移除X个[curse]与X个[bless]：治愈同地点卡牌共X点恐惧。返回治愈量。"""
        bag = self._chaos_bag
        inv = game_state.get_investigator(investigator_id)
        if bag is None or inv is None or x <= 0:
            return 0
        removable = min(
            sum(1 for t in bag.tokens if t == ChaosTokenType.CURSE),
            sum(1 for t in bag.tokens if t == ChaosTokenType.BLESS),
        )
        n = min(int(x), removable)
        healed = 0
        if n > 0:
            for _ in range(n):
                bag.remove(ChaosTokenType.CURSE)
                bag.remove(ChaosTokenType.BLESS)
            # 治愈同地点卡牌（简化：调查员恐惧多者优先）
            pool = n
            targets = sorted(
                game_state.get_investigators_at_location(inv.location_id),
                key=lambda i: -i.horror,
            )
            for target in targets:
                take = min(pool, target.horror)
                target.horror -= take
                pool -= take
                healed += take
                if pool <= 0:
                    break
        return healed

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        mode = ctx.extra.get("mode", "exchange")
        x = int(ctx.extra.get("x", 1) or 1)
        if mode == "heal":
            healed = self.remove_and_heal(
                ctx.game_state, ctx.investigator_id, x)
            ctx.extra["rite_of_equilibrium_healed"] = healed
        else:
            added = self.exchange(ctx.game_state, x)
            ctx.extra["rite_of_equilibrium_added"] = added
