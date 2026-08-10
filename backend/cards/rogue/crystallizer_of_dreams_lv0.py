"""Crystallizer of Dreams (Level 0) — Rogue Asset, Accessory slot. (06024)
作为打出本卡牌的额外费用，你必须在你的绑定卡牌中查找1张结晶器守卫，并将
其混洗入你的牌堆。
[反应]在你打出一张事件卡后：不将其丢弃，改为将其正面朝下叠加到梦境结晶器
（最多叠加5张事件卡）。可以将叠加的事件卡投入技能检定，如同其为你的手牌。

简化说明：
- 绑定卡（结晶器守卫 Guardian of the Crystallizer）的查找/洗牌为额外费用：
  引擎无绑定卡组概念（引擎缺口，见报告）；本实现不处理该费用。
- 叠加时机：引擎在 CARD_PLAYED 结算后才把事件放入弃牌堆，故先在
  CARD_PLAYED 记下待叠加卡，再在紧随的 ACTION_PERFORMED（打出动作）
  从弃牌堆捞起叠加；若打出不经过动作通道，则在下一次 CARD_PLAYED /
  SKILL_TEST_ENDS 时补捞（兜底）。
- "叠加的事件可当作手牌投入检定"需要会话层在投入选择中放行
  impl.attached 中的卡（引擎提交通道只认手牌——引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority

_MAX_ATTACHED = 5


class CrystallizerOfDreams(CardImplementation):
    card_id = "crystallizer_of_dreams_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self.attached: list[str] = []  # 叠加的事件卡（正面朝下）
        self._pending: tuple[str, str] | None = None  # (inv_id, card_id)

    def _owner_inv(self, game_state):
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return None
        inv = game_state.get_investigator(inst.owner_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        return inv

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.REACTION)
    def mark_pending(self, ctx):
        """你打出一张事件后：记下待叠加（引擎随后才将其放入弃牌堆）。"""
        card_id = ctx.extra.get("card_id")
        if not card_id or card_id == self.card_id:
            return
        cd = ctx.game_state.get_card_data(card_id)
        if cd is None or cd.type != CardType.EVENT:
            return
        owner = self._owner_inv(ctx.game_state)
        if owner is None or ctx.investigator_id != owner.investigator_id:
            return
        if len(self.attached) >= _MAX_ATTACHED:
            return
        # 兜底：上一次待叠加的卡尚未入弃牌堆流程时先补捞
        self._collect_pending(ctx.game_state)
        self._pending = (owner.investigator_id, card_id)

    def _collect_pending(self, game_state) -> None:
        """把待叠加事件从拥有者弃牌堆捞起，叠加到本卡。"""
        if self._pending is None:
            return
        inv_id, card_id = self._pending
        self._pending = None
        if len(self.attached) >= _MAX_ATTACHED:
            return
        inv = game_state.get_investigator(inv_id)
        if inv is None or card_id not in inv.discard:
            return
        inv.discard.remove(card_id)
        self.attached.append(card_id)
        game_state.log_effect(
            f"💠 梦境结晶器：叠加【{game_state.card_name(card_id)}】"
            f"（当前{len(self.attached)}张）")

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def attach_after_play_action(self, ctx):
        self._collect_pending(ctx.game_state)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def attach_fallback(self, ctx):
        self._collect_pending(ctx.game_state)

    def can_commit(self, card_id: str) -> bool:
        """会话层投入校验用：该卡是否叠加在本卡上（可当作手牌投入）。"""
        return card_id in self.attached

    def consume_attached(self, game_state, card_id: str) -> bool:
        """会话层用：叠加的事件被投入检定后置入拥有者弃牌堆。"""
        if card_id not in self.attached:
            return False
        self.attached.remove(card_id)
        inst = game_state.get_card_instance(self.instance_id)
        inv = game_state.get_investigator(inst.owner_id) if inst else None
        if inv is not None:
            inv.discard.append(card_id)
        return True
