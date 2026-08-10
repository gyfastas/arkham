"""Ancestral Knowledge (Level 3) — Seeker Asset (Permanent, Exceptional). (07303)
永久。卓越。你的牌组必须包含至少10张技能牌。你的牌组上限+5。
[反应]在你抽取起始手牌前：从你的牌堆中随机附着5张非弱点技能牌到本卡上
（面朝下）。
[快速]横置先祖学识：抽取1张附着的技能牌。

简化说明：
- 永久/卓越/牌组构筑要求（≥10技能、牌组+5）为构筑规则，由构筑/会话层处理；
  对局内实现仅含两个能力。
- 开局附着实现为公开方法 setup_opening()（会话层应在抽取起始手牌前调用）；
  CARD_ENTERS_PLAY 时幂等触发一次（与 stick_to_the_plan 同款既定模式）。
  附着的技能牌已从牌堆移除，记录在 scenario.vars["ancestral_knowledge"]。
- "随机5张"经 random.sample 实现；"抽取1张附着牌"官方为随机（面朝下），
  简化为取第一张，activate(card_id=...) 可显式指定。
"""

import random

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import is_weakness_card

VAR = "ancestral_knowledge"
SETUP_COUNT = 5


class AncestralKnowledge(CardImplementation):
    card_id = "ancestral_knowledge_lv3"
    activations = [{
        "id": "draw_attached",
        "label": "[快速]横置：抽取1张附着的技能牌",
        "method": "activate",
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def on_enters_play(self, ctx):
        """入场时执行开局附着（幂等；官方时机为抽取起始手牌前）。"""
        if ctx.target != self.instance_id:
            return
        self.setup_opening(ctx.game_state, ctx.investigator_id)

    def setup_opening(self, game_state, investigator_id) -> list:
        """[反应]抽取起始手牌前：随机附着5张非弱点技能牌（面朝下）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return []
        store = game_state.scenario.vars.setdefault(VAR, {})
        if store.get(investigator_id) is not None:
            return []  # 已结算过（幂等）

        skills = [
            cid for cid in inv.deck
            if (cd := game_state.get_card_data(cid)) is not None
            and cd.type == CardType.SKILL
            and not is_weakness_card(cd)
        ]
        found = random.sample(skills, min(SETUP_COUNT, len(skills)))
        for cid in found:
            inv.deck.remove(cid)
        store[investigator_id] = found
        if found:
            game_state.log_effect(
                f"🧬 先祖学识：附着{len(found)}张技能牌（面朝下）"
            )
        return found

    def attached_skills(self, game_state, investigator_id) -> list:
        """当前附着在本卡上的技能牌 id 列表。"""
        return list(
            game_state.scenario.vars.get(VAR, {}).get(investigator_id) or [])

    def activate(self, game_state, investigator_id: str,
                 card_id: str | None = None) -> bool:
        """[快速]横置：抽取1张附着的技能牌（简化：缺省取第一张，官方为随机）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        attached = game_state.scenario.vars.get(VAR, {}).get(investigator_id)
        if not attached:
            return False
        chosen = card_id if card_id is not None else attached[0]
        if chosen not in attached:
            return False

        inst.exhausted = True
        attached.remove(chosen)
        inv.hand.append(chosen)
        game_state.log_effect(
            f"🧬 先祖学识：横置，抽取附着的【{game_state.card_name(chosen)}】"
        )
        return True
