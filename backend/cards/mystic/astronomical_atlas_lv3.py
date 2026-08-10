"""Astronomical Atlas (Level 3) — Mystic Asset, Hand slot. (08067)
[fast]消耗天文地图集：查看你牌堆顶部的卡牌。如果其非弱点，将其正面朝下
叠加到天文地图集（最多叠加5张卡牌）。
[fast]：将叠加到天文地图集的一张卡牌投入到一个符合条件的技能检定中。
如果该检定成功，不丢弃该卡牌，改为将其加入你的手牌。（每次检定限1次。）

简化说明：
- attach_top() 消耗本卡并把牌堆顶非弱点卡叠加到本卡（记录在实例的
  attached_cards 列表；弱点则留在牌堆顶——官方"查看后"可选择不叠加，
  简化为非弱点即叠加）。
- commit_attached() 把叠加卡交给会话层投入检定（从叠加列表移除并返回
  card_id，由会话层加入 committed_card_ids）；成功时经 SKILL_TEST_ENDS
  将该卡置入手牌，失败置入弃牌堆（引擎 ST.8 只处理手牌中的投入卡，
  叠加卡由本实现兜底结算去向）。每次检定限1张。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import is_weakness_card

MAX_ATTACHED = 5


class AstronomicalAtlas(CardImplementation):
    card_id = "astronomical_atlas_lv3"
    activations = [
        {"id": "attach_top", "label": "[快速]消耗：牌堆顶非弱点卡叠加到本卡",
         "method": "attach_top"},
        {"id": "commit", "label": "[快速]投入一张叠加卡，成功则回收手牌",
         "method": "commit_attached"},
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attached: list[str] = []
        self._committed: str | None = None

    @property
    def attached_cards(self) -> list[str]:
        return list(self._attached)

    def attach_top(self, game_state, investigator_id: str) -> bool:
        """[fast]消耗：查看牌堆顶，非弱点则叠加到本卡（最多5张）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or len(self._attached) >= MAX_ATTACHED:
            return False
        if not inv.deck:
            return False
        top = inv.deck[0]
        cd = game_state.get_card_data(top)
        if cd is not None and is_weakness_card(cd):
            return False  # 弱点留在牌堆顶（官方查看后可不叠加）
        inst.exhausted = True
        inv.deck.pop(0)
        self._attached.append(top)
        game_state.log_effect(f"🌌 天文地图集：叠加【{game_state.card_name(top)}】")
        return True

    def commit_attached(self, game_state, investigator_id: str,
                        card_id: str | None = None) -> str | None:
        """[fast]将一张叠加卡投入当前检定；返回投入的 card_id 供会话层传入
        run_test(committed_card_ids=...)。每次检定限1张。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return None
        if self._committed is not None or not self._attached:
            return None
        if card_id is None:
            card_id = self._attached[0]
        if card_id not in self._attached:
            return None
        self._attached.remove(card_id)
        self._committed = card_id
        return card_id

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_committed(self, ctx):
        """检定结束：成功则叠加投入卡加入手牌，否则入弃牌堆。"""
        if self._committed is None:
            return
        card_id = self._committed
        self._committed = None
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        if ctx.success:
            inv.hand.append(card_id)
            ctx.extra["astronomical_atlas_returned"] = card_id
            ctx.game_state.log_effect(
                f"🌌 天文地图集：【{ctx.game_state.card_name(card_id)}】回到手牌")
        else:
            inv.discard.append(card_id)

    @on_event(GameEvent.CARD_LEAVES_PLAY, priority=TimingPriority.AFTER)
    def drop_attachments(self, ctx):
        """离场：叠加的卡进入持有者弃牌堆。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            inv.discard.extend(self._attached)
        self._attached.clear()
