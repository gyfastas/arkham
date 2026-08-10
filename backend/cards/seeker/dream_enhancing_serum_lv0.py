"""Dream-Enhancing Serum (Level 0) — Seeker Asset, Arcane slot. (06159)
你手牌中每种卡牌仅有第一份副本计入手牌上限。
[反应]在你抽到一张手牌中已有副本的卡牌后，展示两份副本并横置梦境增强
血清：抽1张牌。

简化说明：
- 手牌上限经 UPKEEP_PHASE_BEGINS 的 limit ctx 上调"重复副本数"实现
  （与 drawing_the_sign 反向同款通道）；"副本"按卡名判定；
- 反应自动触发（官方为玩家选择是否横置；抽牌为纯收益）：抽到的卡与手牌中
  另一张同名时自动横置并补抽1张；
- "展示两份副本"无展示机制，仅记录日志；补抽为静默移动（不经 CARD_DRAWN，
  与 cryptic_research 等直接抽牌一致）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class DreamEnhancingSerum(CardImplementation):
    card_id = "dream_enhancing_serum_lv0"

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.WHEN)
    def loosen_hand_limit(self, ctx):
        """每种卡仅第一份计入手牌上限：上限+重复副本数。"""
        if ctx.investigator_id is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        names = [self._name(ctx.game_state, cid) for cid in inv.hand]
        duplicates = len(names) - len(set(names))
        if duplicates > 0:
            ctx.modify_amount(duplicates, "dream_enhancing_serum_copies")

    @on_event(GameEvent.CARD_DRAWN, priority=TimingPriority.AFTER)
    def draw_on_duplicate(self, ctx):
        """抽到与手牌中已有卡牌同名的卡后：横置本卡，抽1张。"""
        card_id = ctx.extra.get("card_id")
        if not card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if card_id not in inv.hand:
            return
        # 手牌中同名卡（含被抽的这张）≥2 即存在另一副本（兼容同 id 多副本）
        drawn_name = self._name(ctx.game_state, card_id)
        copies = sum(1 for cid in inv.hand
                     if self._name(ctx.game_state, cid) == drawn_name)
        if copies < 2:
            return

        inst.exhausted = True
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        ctx.extra["dream_enhancing_serum_drew"] = True
        ctx.game_state.log_effect(
            f"🧪 梦境增强血清：抽到已有副本的【{drawn_name}】，横置抽1张"
        )

    @staticmethod
    def _name(game_state, card_id) -> str:
        cd = game_state.get_card_data(card_id)
        return (cd.name if cd and cd.name else card_id)
