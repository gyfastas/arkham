"""Seeker 内部工具：卡牌自身发起的简化技能检定（ST 事件序列回放）。

引擎的 SkillTestEngine 只被 actions.py / 会话层持有，卡实现拿不到；
但部分卡面能力本身就是一次检定（Medical Texts 智力(2)、Expose Weakness
智力(X)、Strange Solution 智力(4)）。本 mixin 让卡牌用事件总线按标准
ST.1→ST.8 顺序回放一次检定（ ChaosToken 由 bind_chaos_bag 注入的袋中抽取，
registry.activate_card 已在生产接线），使这类能力在卡文件内闭环。

简化说明（与官方差异）：
- 无 ST.2 投入窗口：玩家不能向这类检定投入技能卡（会话层 pending 检定
  流程才支持投入）；其余修正（在场支援加值、远古印记、自动失败标记等）
  均通过正常事件生效。
"""

from __future__ import annotations

from backend.cards.base import CardImplementation
from backend.models.enums import CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent


class CardSelfTest(CardImplementation):
    """提供 run_self_test() 的基类：注册时暂存事件总线，混沌袋注入。"""

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._selftest_bus = bus

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._selftest_bag = chaos_bag

    def run_self_test(
        self,
        game_state,
        investigator_id: str,
        skill_type,
        difficulty: int,
        source: str | None = None,
    ) -> tuple[bool, int] | None:
        """回放一次简化技能检定。返回 (success, margin)；无总线/袋时返回 None。"""
        bus = getattr(self, "_selftest_bus", None)
        bag = getattr(self, "_selftest_bag", None)
        inv = game_state.get_investigator(investigator_id)
        if bus is None or bag is None or inv is None:
            return None

        from backend.engine.event_bus import EventContext

        def emit(event, **kwargs):
            ctx = EventContext(
                game_state=game_state,
                event=event,
                investigator_id=investigator_id,
                source=source,
                **kwargs,
            )
            bus.emit(ctx)
            return ctx

        # ST.1: 检定开始（允许 Flashlight 等修改难度）
        ctx = emit(GameEvent.SKILL_TEST_BEGINS, skill_type=skill_type, difficulty=difficulty)
        if ctx.difficulty is not None:
            difficulty = max(0, ctx.difficulty)

        # ST.3: 抽取混沌标记
        token = bag.draw()
        emit(
            GameEvent.CHAOS_TOKEN_REVEALED,
            chaos_token=token, skill_type=skill_type, difficulty=difficulty,
        )

        # ST.4: 标记效果（场景符号效果、远古印记能力等经事件生效）
        auto_fail = token == ChaosTokenType.AUTO_FAIL
        modifier = 0 if auto_fail else (CHAOS_TOKEN_VALUES.get(token, 0) or 0)
        ctx = emit(
            GameEvent.CHAOS_TOKEN_RESOLVED,
            chaos_token=token, amount=modifier,
            skill_type=skill_type, difficulty=difficulty,
        )
        modifier = ctx.amount
        if ctx.extra.get("force_auto_fail"):
            auto_fail = True

        # ST.5: 修正后技能值（无投入图标）
        base_skill = inv.get_skill(skill_type)
        value = 0 if auto_fail else max(0, base_skill + modifier)
        ctx = emit(
            GameEvent.SKILL_VALUE_DETERMINED,
            skill_type=skill_type, modified_skill=value, difficulty=difficulty,
            amount=value,
            extra={"base_skill": base_skill, "committed_icons": 0,
                   "token_modifier": modifier},
        )
        value = max(0, ctx.amount)

        # ST.6: 成败判定（允许 Rex's Curse 等翻转结果）
        if auto_fail:
            success = False
        elif difficulty == 0:
            success = True
        else:
            success = value >= difficulty
        event = GameEvent.SKILL_TEST_SUCCESSFUL if success else GameEvent.SKILL_TEST_FAILED
        ctx = emit(
            event,
            skill_type=skill_type, success=success,
            modified_skill=value, difficulty=difficulty,
            amount=modifier, committed_cards=[],
            extra={"base_skill": base_skill, "committed_icons": 0,
                   "token_modifier": modifier, "auto_fail": auto_fail},
        )
        if ctx.success is not None and ctx.success != success:
            success = ctx.success

        # ST.7 / ST.8: 结果应用与收尾（清理各卡的"本次检定"标记）
        emit(GameEvent.SKILL_TEST_APPLY_RESULTS, success=success)
        emit(GameEvent.SKILL_TEST_ENDS, success=success)

        return success, value - difficulty
