"""The Codex of Ages (Level 0) — Neutral Asset. (04013)
仅限马特奥神父牌组。封印（[远古印记]）。
有标记封印在本卡上时，你获得+1[意志]。
[reaction]当你即将从混沌袋中揭示一个混沌标记时，丢弃岁月古抄：结算封印在
本卡上的[远古印记]标记，视其为刚从混沌袋中揭示（代替从混沌袋中揭示标记）。

简化说明：
- "仅限马特奥牌组"为构筑限制，由卡组校验负责。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动绑定）。
- 进场即封印[远古印记]（CARD_ENTERS_PLAY），记录在实例 uses["sealed_elder_sign"]。
- 反应为可选能力：会话层在检定前调用 activate_sealed() 武装并丢弃本卡；
  下一个 CHAOS_TOKEN_RESOLVED 将标记改写为[远古印记]（清零原修正、取消
  自动失败，同 seal_of_the_elder_sign_lv5 惯例），封印标记随之释回袋中。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards._shared import defeat_asset
from backend.models.enums import ChaosTokenType, GameEvent, Skill, TimingPriority


class TheCodexOfAges(CardImplementation):
    card_id = "the_codex_of_ages_lv0"
    activations = [{
        "id": "sealed_token",
        "label": "[反应] 丢弃古抄：将本次揭示视为[远古印记]",
        "method": "activate_sealed",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._armed = False

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry 自动绑定）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_elder_sign(self, ctx):
        """进场：封印（[远古印记]）。"""
        if ctx.target != self.instance_id:
            return
        if self._chaos_bag is None:
            return
        if self._chaos_bag.seal_token(ChaosTokenType.ELDER_SIGN):
            inst = ctx.game_state.get_card_instance(self.instance_id)
            if inst is not None:
                inst.uses["sealed_elder_sign"] = 1

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """有标记封印在本卡上时：+1意志。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is not None and inst.uses.get("sealed_elder_sign", 0) > 0:
            ctx.modify_amount(1, "codex_of_ages_willpower")

    def activate_sealed(self, game_state, investigator_id) -> bool:
        """[reaction] 丢弃本卡：下一次标记揭示改为结算封印的[远古印记]。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.uses.get("sealed_elder_sign", 0) <= 0:
            return False
        self._armed = True
        defeat_asset(game_state, getattr(self, "_bus", None), self.instance_id)
        return True

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def resolve_as_elder_sign(self, ctx):
        """将本次揭示的标记改写为封印的[远古印记]。"""
        if not self._armed:
            return
        self._armed = False
        # 封印的标记被结算：释回混沌袋
        if self._chaos_bag is not None:
            self._chaos_bag.release_token(ChaosTokenType.ELDER_SIGN)
        if ctx.chaos_token != ChaosTokenType.ELDER_SIGN:
            if ctx.amount:
                ctx.modify_amount(-ctx.amount, "codex_of_ages_replace")
            ctx.chaos_token = ChaosTokenType.ELDER_SIGN
            ctx.extra["cancel_auto_fail"] = True
        ctx.extra["codex_of_ages_elder_sign"] = True

    def register(self, bus, instance_id: str) -> None:
        self._bus = bus
        super().register(bus, instance_id)
