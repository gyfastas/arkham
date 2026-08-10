"""A Watchful Peace (Level 3) — Survivor Event.
作为打出的额外费用，从混乱袋和/或场上的卡牌中找出共5个[祝福]标记返回供应堆。
快速。在神话阶段"抽取遭遇卡"步骤即将开始时打出。跳过该步骤。

简化说明：
- 经公开方法 play() 由会话层在神话阶段 1.4 前的玩家窗口调用
  （activations 已声明）：支付1资源、从混乱袋（含袋上封印）移除5个祝福标记
  （返回标记供应堆，即移出游戏），本卡入弃牌堆。
- "跳过抽取遭遇卡步骤"：MythosPhase._draw_encounter_cards 无跳过钩子，
  实现为登记 scenario.vars["skip_encounter_draw_once"] = True，需引擎消费
  该标记（引擎缺口，见报告）。封印在场卡牌上的祝福标记由会话层传入
  sealed_from_cards 计数一并计入5个（卡实现只处理袋内部分）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import ChaosTokenType

_REQUIRED_BLESS = 5


class AWatchfulPeace(CardImplementation):
    card_id = "a_watchful_peace_lv3"
    activations = [{
        "id": "play",
        "label": "快速打出：跳过抽取遭遇卡步骤（额外费用：5祝福）",
        "method": "play",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    def play(self, game_state, investigator_id: str,
             sealed_from_cards: int = 0) -> bool:
        """支付1资源+返回5个祝福标记：跳过神话阶段的抽取遭遇卡步骤。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return False
        cd = game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 1) or 1) if cd else 1
        if inv.resources < cost:
            return False

        bag = self._chaos_bag
        in_bag = 0
        if bag is not None:
            in_bag = sum(1 for t in bag.tokens if t == ChaosTokenType.BLESS)
            in_bag += sum(1 for t in bag.sealed if t == ChaosTokenType.BLESS)
        if in_bag + sealed_from_cards < _REQUIRED_BLESS:
            return False

        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # 返回5个祝福标记到供应堆（优先袋内，其次袋上封印）
        remaining = _REQUIRED_BLESS - sealed_from_cards
        if bag is not None:
            for pool in (bag.tokens, bag.sealed):
                while remaining > 0 and ChaosTokenType.BLESS in pool:
                    pool.remove(ChaosTokenType.BLESS)
                    remaining -= 1

        game_state.scenario.vars["skip_encounter_draw_once"] = True
        game_state.log_effect(
            "🕊️ 警戒和平：返回5个祝福标记，跳过本回合神话阶段的抽取遭遇卡步骤")
        return True
