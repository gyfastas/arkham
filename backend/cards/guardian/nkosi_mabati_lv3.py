"""Nkosi Mabati (Level 3) — Guardian Asset, Ally slot. (08091)
[反应] 在恩科西·马巴提入场后：说出一个非[远古印记]的带符号混乱标记。
直到本卡离场，该符号是你的"印记"。
[反应] 当你所在地点的调查员揭示[教徒]、[石板]或[古老者]符号时，
横置恩科西·马巴提：在混乱袋中查找你的印记并改为揭示它
（将另一个标记放回混乱袋）。

简化说明：
- "说出印记"：自动默认为[骷髅]（可经 ctx.extra["sigil"] 或公开方法
  name_sigil() 指定 skull/cultist/tablet/elder_thing 之一）。
- 换标记在 CHAOS_TOKEN_RESOLVED（WHEN）结算：把 ctx.chaos_token 改为印记、
  修正数值并标记 extra（同 favor_of_the_moon 的换标记约定；剧本的符号
  效果监听若在同事件更晚优先级，将看到换入的印记）。
- 引擎抽标记不离袋，"放回/查找"的袋子记账无需变动（注明）。
- 印记标记若本身是自动失败则取消自动失败（防御性，印记不可选远古印记，
  实际不会触发）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CHAOS_TOKEN_VALUES, ChaosTokenType, GameEvent, TimingPriority,
)

_TRIGGER_TOKENS = {
    ChaosTokenType.CULTIST, ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}
_SIGIL_CHOICES = {
    ChaosTokenType.SKULL, ChaosTokenType.CULTIST,
    ChaosTokenType.TABLET, ChaosTokenType.ELDER_THING,
}


class NkosiMabati(CardImplementation):
    card_id = "nkosi_mabati_lv3"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._sigil: ChaosTokenType | None = None

    def name_sigil(self, game_state, sigil) -> bool:
        """(会话层可调用) 指定印记符号。"""
        sigil = ChaosTokenType(sigil) if not isinstance(sigil, ChaosTokenType) else sigil
        if sigil not in _SIGIL_CHOICES:
            return False
        self._sigil = sigil
        game_state.log_effect(f"🧿 恩科西·马巴提：印记为[{sigil.value}]")
        return True

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.REACTION)
    def choose_sigil(self, ctx):
        """入场后：说出印记（默认[骷髅]，可经 extra["sigil"] 指定）。"""
        if ctx.target != self.instance_id:
            return
        sigil = ctx.extra.get("sigil")
        if sigil is not None:
            try:
                sigil = ChaosTokenType(sigil)
            except ValueError:
                sigil = None
        if sigil not in _SIGIL_CHOICES:
            sigil = ChaosTokenType.SKULL
        self._sigil = sigil
        ctx.extra["nkosi_sigil"] = sigil.value
        ctx.game_state.log_effect(f"🧿 恩科西·马巴提：印记为[{sigil.value}]")

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def swap_token(self, ctx):
        """同地点调查员揭示教徒/石板/古老者：横置，改为揭示印记。"""
        if ctx.chaos_token not in _TRIGGER_TOKENS or self._sigil is None:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        owner = ctx.game_state.get_investigator(inst.controller_id)
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if owner is None or inv is None:
            return
        if self.instance_id not in owner.play_area:
            return
        if inv.location_id != owner.location_id:
            return

        inst.exhausted = True
        original = ctx.chaos_token
        ctx.chaos_token = self._sigil
        value = CHAOS_TOKEN_VALUES.get(self._sigil)
        if value is not None:
            ctx.modify_amount(value - (ctx.amount or 0), "nkosi_sigil_swap")
        else:
            # 符号标记的场景值由剧本监听结算；换入符号时归零原数值修正，
            # 由剧本对换入符号重新处理（同 favor_of_the_moon 约定）
            ctx.modify_amount(-(ctx.amount or 0), "nkosi_sigil_swap")
        ctx.extra["nkosi_swapped"] = getattr(original, "value", str(original))
        ctx.game_state.log_effect(
            f"🧿 恩科西·马巴提：横置，[{getattr(original, 'value', original)}]"
            f"改为揭示印记[{self._sigil.value}]")

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def clear_sigil(self, ctx):
        if ctx.target == self.instance_id:
            self._sigil = None
