"""Preston Fairmont — Rogue Investigator.
能力：每当你从一个卡牌效果获得1个或多个资源，不将其放在资源池，改为放在
家族遗产上。
远古印记：+0。你可以花费2资源来改为自动成功。

简化说明：
- "从卡牌效果获得资源"：引擎的卡牌效果普遍直接 inv.resources += N 且不发
  事件（RESOURCES_GAINED 仅由资源行动与补给阶段发出——二者是框架效果，
  官方本就不转移），无拦截钩子（引擎缺口）。实现为公开方法
  redirect_gain()，由会话层在卡牌效果发放资源时调用；家族遗产未入场时
  回退到资源池并返回 False（永久物开局入场引擎未建模，见
  family_inheritance_lv0）。
- 家族遗产上的资源经其实例 uses["resources"] 存放（同 family_inheritance_lv0
  既定约定），官方规则中可像资源池一样花费。
- 远古印记的"你可以花费2资源"：简化为有足够可花费资源（资源池+家族遗产）
  时自动花费（先扣资源池，不足部分扣家族遗产）并自动成功；
  scenario.vars["preston_fairmont_decline_auto_success"] = True 可放弃。
  "自动成功"在 SKILL_TEST_FAILED 时把 ctx.success 置 True（引擎 ST.6 据此
  翻转结果）。
- 马泰奥神父将自动失败转为远古印记时（father_mateo_converted 标记），本卡
  同样按远古印记结算。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

FAMILY_INHERITANCE_ID = "family_inheritance_lv0"
AUTO_SUCCESS_COST = 2


class PrestonFairmont(CardImplementation):
    card_id = "preston_fairmont"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._auto_success = False

    def _get_preston(self, game_state, investigator_id):
        """Return the investigator state iff it is Preston Fairmont."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "preston_fairmont":
            return None
        return inv

    def _find_inheritance(self, game_state, inv):
        """普雷斯顿场上的家族遗产实例。"""
        for inst_id in inv.play_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == FAMILY_INHERITANCE_ID:
                return inst
        return None

    def redirect_gain(self, game_state, investigator_id, amount: int) -> bool:
        """卡牌效果发放资源时调用：改为放在家族遗产上。

        返回 True 表示已放到家族遗产；家族遗产未入场时回退到资源池并
        返回 False。
        """
        inv = self._get_preston(game_state, investigator_id)
        if inv is None or amount <= 0:
            return False
        inst = self._find_inheritance(game_state, inv)
        if inst is None:
            inv.resources += amount
            return False
        inst.uses["resources"] = inst.uses.get("resources", 0) + amount
        game_state.log_effect(
            f"💰 普雷斯顿·费尔蒙特：{amount}资源放到家族遗产上"
        )
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+0。可花费2资源改为自动成功（资源池+家族遗产）。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN \
                and not ctx.extra.get("father_mateo_converted"):
            return
        inv = self._get_preston(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is not None \
                and scenario.vars.get("preston_fairmont_decline_auto_success"):
            return

        inst = self._find_inheritance(ctx.game_state, inv)
        fi_resources = inst.uses.get("resources", 0) if inst is not None else 0
        if inv.resources + fi_resources < AUTO_SUCCESS_COST:
            return

        from_pool = min(inv.resources, AUTO_SUCCESS_COST)
        inv.resources -= from_pool
        rest = AUTO_SUCCESS_COST - from_pool
        if rest:
            inst.uses["resources"] -= rest
        self._auto_success = True
        ctx.game_state.log_effect(
            "💰 普雷斯顿·费尔蒙特：远古印记，花费2资源改为自动成功"
        )

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def apply_auto_success(self, ctx):
        """远古印记：检定失败时翻转为成功。"""
        if not self._auto_success:
            return
        if self._get_preston(ctx.game_state, ctx.investigator_id) is None:
            return
        ctx.success = True
        ctx.extra["preston_fairmont_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_auto_success(self, ctx):
        self._auto_success = False
