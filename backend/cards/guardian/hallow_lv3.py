"""Hallow (Level 3) — Guardian Event. (07301)
作为打出圣化的额外费用，从混乱袋或场上卡牌封印的标记中，
将合计10个[祝福]标记返回供应堆。
移除场上任意一张卡牌上的1点毁灭。

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
- "封印在场上卡牌的标记"以混沌袋的 sealed 列表表示（本引擎封印流程
  统一经 bag.seal_token 移入 sealed）。优先从袋中返还，不足再从封印中返还；
  合计不足10个时效果不结算（官方为根本无法打出，由会话层前置校验）。
- "任意一张卡牌上的1点毁灭"自动选择：优先剧情卡（doom_on_agenda），
  其次第一张带毁灭的场上卡牌/地点；可经 ctx.extra["doom_target"]
  （instance_id / "agenda" / location_id）指定。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

_COST_TOKENS = 10


class Hallow(CardImplementation):
    card_id = "hallow_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._bag = chaos_bag

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def resolve(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        if self._bag is None:
            return

        in_bag = self._bag.tokens.count(ChaosTokenType.BLESS)
        sealed = self._bag.sealed.count(ChaosTokenType.BLESS)
        if in_bag + sealed < _COST_TOKENS:
            ctx.extra["hallow_fizzle"] = True
            ctx.game_state.log_effect(
                "🕊️ 圣化：祝福标记不足10个，效果不结算（官方无法打出）")
            return

        # 额外费用：10个祝福标记返回供应堆（先袋中，后封印）
        remaining = _COST_TOKENS
        while remaining and self._bag.remove(ChaosTokenType.BLESS):
            remaining -= 1
        while remaining:
            try:
                self._bag.sealed.remove(ChaosTokenType.BLESS)
                remaining -= 1
            except ValueError:
                break

        # 移除1点毁灭
        removed = self._remove_doom(ctx)
        ctx.extra["hallow_doom_removed"] = removed
        ctx.game_state.log_effect(
            f"🕊️ 圣化：10个祝福标记返回供应堆，移除{removed}上的1点毁灭")

    def _remove_doom(self, ctx) -> str:
        """移除1点毁灭，返回目标描述。"""
        scenario = ctx.game_state.scenario
        target = ctx.extra.get("doom_target")
        if target == "agenda" or target is None:
            if scenario.doom_on_agenda > 0:
                scenario.doom_on_agenda -= 1
                return "剧情"
            if target == "agenda":
                return "剧情（无毁灭）"
        elif target is not None:
            inst = ctx.game_state.get_card_instance(target)
            if inst is not None and inst.doom > 0:
                inst.doom -= 1
                return f"【{ctx.game_state.card_name(inst.card_id)}】"
            loc = ctx.game_state.get_location(target)
            if loc is not None and loc.doom > 0:
                loc.doom -= 1
                return f"地点【{ctx.game_state.card_name(target)}】"

        # 自动选择：剧情 → 场上卡牌 → 地点
        if target is None:
            for inst in ctx.game_state.cards_in_play.values():
                if inst.doom > 0:
                    inst.doom -= 1
                    return f"【{ctx.game_state.card_name(inst.card_id)}】"
            for loc in ctx.game_state.locations.values():
                if loc.doom > 0:
                    loc.doom -= 1
                    return f"地点【{ctx.game_state.card_name(loc.location_id)}】"
        return "无（场上没有毁灭）"
