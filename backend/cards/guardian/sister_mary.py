"""Sister Mary — Guardian Investigator.
能力：在设置期间，加入2个[bless]标记到混乱袋。
[reaction]在一轮结束时：加入1个[bless]标记到混乱袋。
远古印记：+1。如果你成功，加入1个[bless]标记到混乱袋。

实现说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线；Game.setup()
  激活调查员实现时传入，生产时序为 apply_scenario_to_game 构建官方袋之后），
  绑定时即加入2个祝福标记（"设置期间"），幂等（_setup_tokens_added 标记）。
- "一轮结束时"与"如果你成功"的祝福标记加入均依赖已注入的混沌袋；未绑定
  （理论上不会发生，测试需手动 bind）时静默跳过。
- 远古印记的成功判定经 SKILL_TEST_SUCCESSFUL（ST.6），远古印记揭示与成功
  之间经 _bless_on_success 标记跨事件传递，SKILL_TEST_ENDS 时清除。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority

SETUP_BLESS_TOKENS = 2


class SisterMary(CardImplementation):
    card_id = "sister_mary"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._setup_tokens_added = False
        self._bless_on_success = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry.activate_card / 测试接线），并加入设置的2个祝福标记。"""
        self._chaos_bag = chaos_bag
        if not self._setup_tokens_added:
            self._setup_tokens_added = True
            for _ in range(SETUP_BLESS_TOKENS):
                chaos_bag.add_token(ChaosTokenType.BLESS)

    def _get_mary(self, game_state, investigator_id):
        """Return the investigator state iff it is Sister Mary."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "sister_mary":
            return None
        return inv

    def _add_bless(self, game_state, reason: str) -> None:
        if self._chaos_bag is None:
            return
        self._chaos_bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect(f"⛪ 玛丽修女：{reason}，加入1个祝福标记到混乱袋")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def add_bless_at_round_end(self, ctx):
        """一轮结束时：加入1个祝福标记到混乱袋。"""
        self._add_bless(ctx.game_state, "一轮结束")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def elder_sign_effect(self, ctx):
        """远古印记：+1。如果此次检定成功，加入1个祝福标记到混乱袋。"""
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        inv = self._get_mary(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(1, "sister_mary_elder_sign")
        self._bless_on_success = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def elder_sign_bless_on_success(self, ctx):
        """远古印记检定成功：加入1个祝福标记到混乱袋。"""
        if not self._bless_on_success:
            return
        self._bless_on_success = False
        if self._get_mary(ctx.game_state, ctx.investigator_id) is None:
            return
        self._add_bless(ctx.game_state, "远古印记检定成功")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_elder_sign_pending(self, ctx):
        self._bless_on_success = False
