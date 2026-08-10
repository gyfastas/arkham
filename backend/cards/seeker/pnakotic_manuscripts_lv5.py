"""Pnakotic Manuscripts (Level 5) — Seeker Asset, Hand slot. (04307)
使用(3秘密)。
[反应]在你所在地点有调查员将要在显现效果期间执行一次技能检定时，
花费1秘密：该检定中不抽出混乱标记。
[行动]花费1秘密：选择你所在地点的1位调查员。该调查员在本轮执行
下一次技能检定时不抽出混乱标记。

简化说明：
- 引擎的检定流程总会抽取标记（无"不抽标记"通道，引擎缺口）；"不抽出"
  以标记效果归零实现：CHAOS_TOKEN_RESOLVED 时把标记修正改为0、并取消
  自动失败（经 cancel_auto_fail 通道），符号标记的场景效果需场景代码
  同样经该事件结算才能一并跳过；
- [行动]能力为 activate()（activations 声明），目标默认同地点的你，可传
  target_investigator_id；[反应]能力为公开方法 skip_revelation_test()
  （引擎无"显现检定"标记，由会话/剧本层在发起显现检定前调用）；
- 数据 JSON 中 uses 键为 "secretss"（上游笔误），读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


def _secrets(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class PnakoticManuscripts(CardImplementation):
    card_id = "pnakotic_manuscripts_lv5"
    activations = [{
        "id": "skip_tokens",
        "label": "[行动]花1秘密：同地点调查员下次检定不抽标记（本轮）",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 待跳过标记的调查员集合（本轮下一次检定生效）
        self._armed: set[str] = set()

    def _spend_secret(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        key = _secrets(inst)
        if inst.uses.get(key, 0) <= 0:
            return False
        inst.uses[key] -= 1
        return True

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None) -> bool:
        """[行动]花费1秘密：目标调查员本轮下次检定不抽标记。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False
        if not self._spend_secret(game_state, investigator_id):
            return False
        self._armed.add(target.investigator_id)
        game_state.log_effect(
            f"📖 纳克特手稿：{target.investigator_id}本轮下次检定不抽标记")
        return True

    def skip_revelation_test(self, game_state, investigator_id: str) -> bool:
        """[反应]显现效果期间的检定：花费1秘密，该检定不抽标记。"""
        if not self._spend_secret(game_state, investigator_id):
            return False
        self._armed.add(investigator_id)
        game_state.log_effect("📖 纳克特手稿：显现检定不抽标记")
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def nullify_token(self, ctx):
        """不抽出标记：标记修正归零、取消自动失败。"""
        if ctx.investigator_id not in self._armed:
            return
        self._armed.discard(ctx.investigator_id)
        if ctx.amount:
            ctx.modify_amount(-ctx.amount, "pnakotic_manuscripts_skip")
        ctx.extra["cancel_auto_fail"] = True
        ctx.extra["pnakotic_manuscripts_skipped"] = True
        ctx.game_state.log_effect("📖 纳克特手稿：本次检定不抽出混乱标记")

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def expire(self, ctx):
        """[行动]能力的"本轮"结束：未消耗的武装清除。"""
        self._armed.clear()
