"""Wendy Adams — Survivor Investigator.
能力：当你揭示一个混沌标记时，从手牌中弃掉1张牌：取消该混沌标记并放回混沌袋中，
然后揭示一个新的混沌标记。（每次检定限制1次。）
远古印记：+0。如果温蒂的护身符在场上，则改为自动成功。

简化说明（完整重抽机制无法在不修改 engine/skill_test.py 的前提下安全实现）：
- 技能检定为同步流程，CHAOS_TOKEN_REVEALED 与 CHAOS_TOKEN_RESOLVED 之间无法等待玩家
  输入。揭示标记时设置 pending_choice（参考 zoey_samaras 模式，供 UI 展示选项）；
  实际"取消+重抽"由公开方法 resolve_cancel() 执行（server 端 pending_choice 解析未接入
  本 kind，需 UI/测试直接调用；resolve_cancel 会弃掉所选手牌并"武装"重抽）。
- 重抽在随后的 CHAOS_TOKEN_RESOLVED 中生效：用 redraw_provider 回调取得新标记
  （可注入 game.chaos_bag.draw；未注入时使用独立随机的标准混沌袋），将其数值修正
  替换 ctx.amount。引擎的 ChaosBag.draw() 不会从袋中移除标记，因此"放回混沌袋"
  在此模型下是 no-op。
- 重抽后的标记只应用数值修正，不再触发符号类效果；若重抽为 AUTO_FAIL，仅按 0 处理
  并在 ctx.extra["wendy_adams_redrawn_auto_fail"] 标记（引擎的 auto_fail 在事件发出前
  已锁定，无法回溯设置）。
- 远古印记"自动成功"以 SKILL_VALUE_DETERMINED +999 近似（引擎无自动成功通道）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.chaos import STANDARD_BAG
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)


class WendyAdams(CardImplementation):
    card_id = "wendy_adams"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._used_this_test = False
        self._redraw_armed = False
        self._amulet_auto_success = False
        # 可注入的重抽来源，例如 game.chaos_bag.draw；测试可注入固定值
        self.redraw_provider = None
        self._fallback_rng = random.Random()

    def _get_wendy(self, game_state, investigator_id):
        """Return the investigator state iff it is Wendy Adams."""
        if investigator_id is None:
            return None
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return None
        card_data = getattr(inv, "card_data", None)
        if card_data is None or card_data.id != "wendy_adams":
            return None
        return inv

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def reset_test_limit(self, ctx):
        """每次检定开始时重置限次与临时状态。"""
        self._used_this_test = False
        self._redraw_armed = False
        self._amulet_auto_success = False

    @on_event(GameEvent.CHAOS_TOKEN_REVEALED, priority=TimingPriority.WHEN)
    def offer_token_cancel(self, ctx):
        """揭示混沌标记时：若有手牌，设置 pending_choice 提供"弃1牌取消并重抽"选项。"""
        if self._used_this_test:
            return
        inv = self._get_wendy(ctx.game_state, ctx.investigator_id)
        if inv is None or not inv.hand:
            return

        scenario = getattr(ctx.game_state, "scenario", None)
        if scenario is None:
            return

        self._used_this_test = True

        token_name = getattr(ctx.chaos_token, "value", str(ctx.chaos_token))
        options = []
        for card_id in dict.fromkeys(inv.hand):  # 去重并保持顺序
            card_data = ctx.game_state.get_card_data(card_id)
            card_name = getattr(card_data, "name_cn", None) or getattr(card_data, "name", card_id)
            options.append({
                "id": card_id,
                "label": f"弃掉【{card_name}】，取消该标记并重新揭示",
            })
        options.append({"id": "decline", "label": "不触发"})

        scenario.vars["pending_choice"] = {
            "kind": "wendy_adams_token_cancel",
            "investigator_id": ctx.investigator_id,
            "token": token_name,
            "prompt": f"<b>温蒂·亚当斯</b>：你揭示了【{token_name}】，是否弃1张手牌取消该标记并重新揭示？",
            "options": options,
        }

    def resolve_cancel(self, game_state, investigator_id, card_id) -> bool:
        """执行取消：弃掉所选手牌，并武装重抽（在下一次 CHAOS_TOKEN_RESOLVED 生效）。

        由 UI 在玩家选择 pending_choice 中的选项后调用。
        """
        inv = self._get_wendy(game_state, investigator_id)
        if inv is None:
            return False
        if card_id not in inv.hand:
            return False

        inv.hand.remove(card_id)
        inv.discard.append(card_id)

        scenario = getattr(game_state, "scenario", None)
        if scenario is not None:
            pending = scenario.vars.get("pending_choice", {})
            if pending.get("kind") == "wendy_adams_token_cancel":
                scenario.vars.pop("pending_choice", None)

        self._redraw_armed = True
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_token(self, ctx):
        """应用重抽结果 / 远古印记效果。"""
        inv = self._get_wendy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return

        # 取消后的重抽：替换数值修正
        if self._redraw_armed:
            self._redraw_armed = False
            if self.redraw_provider is not None:
                new_token = self.redraw_provider()
            else:
                new_token = self._fallback_rng.choice(list(STANDARD_BAG))
            new_value = CHAOS_TOKEN_VALUES.get(new_token) or 0
            ctx.modify_amount(new_value - ctx.amount, "wendy_adams_redraw")
            ctx.extra["wendy_adams_redrawn_token"] = new_token
            if new_token == ChaosTokenType.AUTO_FAIL:
                ctx.extra["wendy_adams_redrawn_auto_fail"] = True
            return

        # 远古印记：+0。如果温蒂的护身符在场上，则改为自动成功。
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            return
        for inst_id in inv.play_area:
            inst = ctx.game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "wendys_amulet":
                self._amulet_auto_success = True
                break

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def amulet_auto_success(self, ctx):
        """温蒂的护身符：以 +999 近似"自动成功"。"""
        if not self._amulet_auto_success:
            return
        inv = self._get_wendy(ctx.game_state, ctx.investigator_id)
        if inv is None:
            return
        ctx.modify_amount(999, "wendys_amulet_auto_success")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear_test_state(self, ctx):
        self._redraw_armed = False
        self._amulet_auto_success = False
