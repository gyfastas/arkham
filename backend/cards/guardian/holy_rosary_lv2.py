"""Holy Rosary (Level 2) — Guardian Asset, Accessory slot. (07220)
你获得+1[意志]。
[反应] 在你于一张诡计卡的意志检定中成功后，横置圣洁念珠：
向混乱袋中加入2个[祝福]标记。

简化说明：
- "诡计卡的意志检定"在引擎事件流中没有标记（剧本经 run_test 跑检定，
  ctx 不携带诡计来源——引擎缺口）。实现识别两种会话标记：
  ctx.extra["treachery_test"] / ctx.extra["treachery_card_id"]，
  或 ctx.source 指向类型为诡计的卡牌实例；另提供公开方法
  on_treachery_willpower_success() 供剧本/会话层直接调用。
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动接线）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    CardType, ChaosTokenType, GameEvent, Skill, TimingPriority,
)


class HolyRosary(CardImplementation):
    card_id = "holy_rosary_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入游戏混沌袋（registry.activate_card 自动调用）。"""
        self._bag = chaos_bag

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def willpower_bonus(self, ctx):
        """+1 意志（在场时）。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and self.instance_id in inv.play_area:
            ctx.modify_amount(1, "holy_rosary_willpower_bonus")

    def _add_bless(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted or self._bag is None:
            return False
        inst.exhausted = True
        for _ in range(2):
            self._bag.add_token(ChaosTokenType.BLESS)
        game_state.log_effect("📿 圣洁念珠：横置，向混乱袋加入2个祝福标记")
        return True

    def on_treachery_willpower_success(self, game_state, investigator_id: str) -> bool:
        """[反应]（会话/剧本层调用）诡计意志检定成功后：横置加2祝福。"""
        return self._add_bless(game_state, investigator_id)

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.REACTION)
    def on_success(self, ctx):
        """诡计意志检定成功（带会话标记时）：横置加2祝福。"""
        if ctx.skill_type != Skill.WILLPOWER:
            return
        is_treachery_test = bool(
            ctx.extra.get("treachery_test") or ctx.extra.get("treachery_card_id")
        )
        if not is_treachery_test and ctx.source:
            src = ctx.game_state.get_card_instance(ctx.source)
            if src is not None:
                data = ctx.game_state.get_card_data(src.card_id)
                is_treachery_test = (
                    data is not None and data.type == CardType.TREACHERY
                )
        if not is_treachery_test:
            return
        if self._add_bless(ctx.game_state, ctx.investigator_id):
            ctx.extra["holy_rosary_bless"] = 2
