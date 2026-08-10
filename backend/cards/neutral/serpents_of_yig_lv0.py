"""Serpents of Yig (Level 0) — Neutral Enemy, Signature Weakness (Father Mateo). (04014)
猎物 - 仅限马特奥神父。猎手。
显现 - 从混沌袋中找到[远古印记]混沌标记并将其封印在伊格之蛇上。

简化说明：
- 混沌袋经 bind_chaos_bag() 注入（registry.activate_card 自动绑定）；
  未绑定时显现效果不触发。
- 敌人生成/交战通道未接线（同 graveyard_ghouls_lv0 的说明），由会话层负责；
  本实现处理封印本身以及伊格之蛇离场时标记的释放。
- 封印记录在所找到的伊格之蛇实例的 uses["sealed_elder_sign"]；找不到在场
  实例时登记 scenario.vars["serpents_of_yig_sealed"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class SerpentsOfYig(CardImplementation):
    card_id = "serpents_of_yig_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        """注入混沌袋（registry 自动绑定）。"""
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation_seal_elder_sign(self, ctx):
        """显现：从混沌袋封印[远古印记]到伊格之蛇上。"""
        if ctx.extra.get("card_id") != "serpents_of_yig_lv0":
            return
        if self._chaos_bag is None:
            return
        if not self._chaos_bag.seal_token(ChaosTokenType.ELDER_SIGN):
            return  # 袋中无远古印记（极罕见：已被封印）
        # vars 标记作为唯一事实来源（实例可能先于 CARD_LEAVES_PLAY 被移除）；
        # 实例上的 uses 仅供 UI 展示。
        ctx.game_state.scenario.vars["serpents_of_yig_sealed"] = True
        inst = self._find_in_play(ctx.game_state)
        if inst is not None:
            inst.uses["sealed_elder_sign"] = 1
        ctx.extra["serpents_of_yig_sealed_elder_sign"] = True

    @on_event(GameEvent.ENEMY_DEFEATED, priority=TimingPriority.AFTER)
    def release_on_defeat(self, ctx):
        """伊格之蛇被击败：释放其上的远古印记回混沌袋。"""
        if ctx.extra.get("card_id") != "serpents_of_yig_lv0":
            return
        self._release(ctx)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def release_on_leave(self, ctx):
        if ctx.extra.get("card_id") != "serpents_of_yig_lv0":
            return
        self._release(ctx)

    def _release(self, ctx) -> None:
        if self._chaos_bag is None:
            return
        if ctx.game_state.scenario.vars.pop("serpents_of_yig_sealed", None):
            self._chaos_bag.release_token(ChaosTokenType.ELDER_SIGN)
        inst = self._find_in_play(ctx.game_state)
        if inst is not None:
            inst.uses.pop("sealed_elder_sign", None)

    @staticmethod
    def _find_in_play(game_state):
        for iid, inst in game_state.cards_in_play.items():
            if inst.card_id == "serpents_of_yig_lv0":
                return inst
        return None
