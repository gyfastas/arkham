"""Stick to the Plan (Level 3) — Guardian Asset (Permanent, Exceptional). (03264)
永久。卓越。
[反应]在你抽取起始手牌前：在你的牌堆中查找最多3张不同的策略和/或供给
事件卡，将其面朝下叠加到原定计划。混洗你的牌堆。
叠加到原定计划的卡牌可以视为在你的手牌中打出。消耗原定计划作为打出
叠加卡牌的额外费用。

简化说明：
- "永久/卓越"为牌组构筑规则（开局即在场、每卡组限1），由会话/构筑层处理。
- 起始手牌前的查找实现为公开方法 setup_opening()（会话层应在抽起始手牌前
  调用）；CARD_ENTERS_PLAY 时也会幂等触发一次。"不同"按卡名去重。
- 叠加关系记录在 scenario.vars["stick_to_the_plan"]（{investigator_id:
  [card_id, ...]}），叠加卡已从牌堆移除。
- 打出叠加卡：引擎卡牌代码无法触发完整打出流程（无法访问 ActionResolver/
  CardRegistry），play_attached() 实现为"消耗（横置）原定计划并把叠加卡
  移入手牌"，随后按正常流程支付资源费用打出；横置费用在移出时支付
  （官方为打出时支付，注明）。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

VAR = "stick_to_the_plan"


class StickToThePlan(CardImplementation):
    card_id = "stick_to_the_plan_lv3"
    activations = [{
        "id": "play_attached",
        "label": "消耗原定计划：将一张叠加卡移入手牌",
        "method": "play_attached",
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def on_enters_play(self, ctx):
        """入场时执行开局查找（幂等；官方时机为抽取起始手牌前）。"""
        if ctx.target != self.instance_id:
            return
        self.setup_opening(ctx.game_state, ctx.investigator_id)

    def setup_opening(self, game_state, investigator_id) -> list:
        """[反应]抽取起始手牌前：查找至多3张不同的策略/供给事件叠加，洗牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return []
        store = game_state.scenario.vars.setdefault(VAR, {})
        if store.get(investigator_id) is not None:
            return []  # 已结算过（幂等）

        found = []
        found_names = set()
        for card_id in list(inv.deck):
            if len(found) >= 3:
                break
            data = game_state.get_card_data(card_id)
            if data is None or data.type != CardType.EVENT:
                continue
            traits = data.traits or []
            if "tactic" not in traits and "supply" not in traits:
                continue
            if data.name in found_names:
                continue
            found.append(card_id)
            found_names.add(data.name)
            inv.deck.remove(card_id)

        random.shuffle(inv.deck)
        store[investigator_id] = found
        if found:
            names = "、".join(game_state.card_name(c) for c in found)
            game_state.log_effect(f"📋 原定计划：叠加【{names}】，混洗牌堆")
        return found

    def attached_cards(self, game_state, investigator_id) -> list:
        """当前叠加在本卡上的事件卡 id 列表。"""
        return list(game_state.scenario.vars.get(VAR, {}).get(investigator_id) or [])

    def play_attached(self, game_state, investigator_id, card_id) -> bool:
        """消耗原定计划，将一张叠加卡移入手牌（随后按正常流程打出）。"""
        attached = game_state.scenario.vars.get(VAR, {}).get(investigator_id) or []
        if card_id not in attached:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        # 找到场上的原定计划并消耗（横置）作为额外费用
        plan = None
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            if inst is not None and inst.card_id == self.card_id:
                plan = inst
                break
        if plan is None or plan.exhausted:
            return False
        plan.exhausted = True
        attached.remove(card_id)
        inv.hand.append(card_id)
        game_state.log_effect(
            f"📋 原定计划：消耗，【{game_state.card_name(card_id)}】移入手牌")
        return True
