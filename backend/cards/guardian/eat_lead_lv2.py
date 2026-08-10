""""Eat lead!" (Level 2) — Guardian Event. (03304)
快速。在你启动一张枪械支援卡上的攻击能力时打出。
你可以花费该支援卡上额外X子弹。本次攻击中，在你抽取混乱标记时，额外抽取
X个混乱标记。选择其中一个结算，忽略其余标记。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：以你装备区枪械的攻击能力发起
  攻击时，若手牌中有本卡且该枪械还有额外子弹，自动打出。
- X 简化为"花光该枪械剩余子弹"（最有利分支；发起事件上下文可经
  ctx.extra["eat_lead_x"] 指定其他值）。
- 自动选择结算值最高的标记：自动失败视为最差，古老者印记视为最好，其余
  符号标记按0计（其场景效果不会针对换入的标记重新结算——引擎缺口：
  换标记后缺少重新结算场景标记效果的通道）。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 已接线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


def _token_rank(token) -> int:
    """自动选择的标记评分：越高越好。"""
    if token == ChaosTokenType.AUTO_FAIL:
        return -999
    if token == ChaosTokenType.ELDER_SIGN:
        return 999
    return CHAOS_TOKEN_VALUES.get(token) or 0


class EatLead(CardImplementation):
    card_id = "eat_lead_lv2"
    persistent_in_hand = True  # 手牌中持续监听攻击发起

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._chaos_bag = None
        self._armed = None  # {"inv": str, "weapon": str, "x": int}

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def auto_play(self, ctx):
        """以你的枪械发起攻击时：自动打出，花费额外X子弹。"""
        weapon_iid = ctx.source
        if weapon_iid is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        if weapon_iid not in inv.play_area:
            return
        weapon = ctx.game_state.get_card_instance(weapon_iid)
        weapon_data = ctx.game_state.get_card_data(weapon.card_id) if weapon else None
        if weapon_data is None or "firearm" not in (weapon_data.traits or []):
            return
        extra_ammo = weapon.uses.get("ammo", 0)
        if extra_ammo <= 0:
            return  # 没有额外子弹可花，不自动打出
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 0) or 0) if data else 0
        if inv.resources < cost:
            return

        # 从手牌打出（支付费用）
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # 花费额外X子弹（简化：默认花光）
        x = ctx.extra.get("eat_lead_x") or extra_ammo
        x = max(0, min(int(x), extra_ammo))
        weapon.uses["ammo"] -= x
        self._armed = {"inv": inv.investigator_id, "weapon": weapon_iid, "x": x}
        ctx.extra["eat_lead_x"] = x
        ctx.game_state.log_effect(f"🔥 吃子弹吧！：额外花费{x}子弹，攻击将多抽{x}个标记")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def choose_token(self, ctx):
        """额外抽取X个标记，选择结算值最高的一个，忽略其余。"""
        armed = self._armed
        if armed is None:
            return
        if ctx.investigator_id != armed["inv"] or ctx.source != armed["weapon"]:
            return
        self._armed = None
        x = armed["x"]
        if x <= 0 or self._chaos_bag is None:
            return

        drawn = [self._chaos_bag.draw() for _ in range(x)]
        original = ctx.chaos_token
        candidates = [original] + drawn
        # max 保持并列时的第一个（原标记优先，等同"忽略其余"）
        best = max(candidates, key=_token_rank)
        ctx.extra["eat_lead_extra_tokens"] = [getattr(t, "value", str(t)) for t in drawn]
        ctx.extra["eat_lead_chose"] = getattr(best, "value", str(best))
        if best is original:
            ctx.game_state.log_effect("🔥 吃子弹吧！：保留原标记，忽略额外标记")
            return

        ctx.chaos_token = best
        value = CHAOS_TOKEN_VALUES.get(best)
        ctx.amount = value if value is not None else 0
        if best == ChaosTokenType.AUTO_FAIL:
            ctx.extra["force_auto_fail"] = True
        if original == ChaosTokenType.AUTO_FAIL and best != ChaosTokenType.AUTO_FAIL:
            ctx.extra["cancel_auto_fail"] = True
        ctx.game_state.log_effect(
            f"🔥 吃子弹吧！：选择结算【{getattr(best, 'value', best)}】，忽略其余{x}个标记")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def disarm(self, ctx):
        self._armed = None
