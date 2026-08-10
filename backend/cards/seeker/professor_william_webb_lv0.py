"""Professor William Webb (Level 0) — Seeker Asset, Ally slot. (08104)
使用(3秘密)。
[反应]在你成功调查时，消耗威廉·韦伯教授并花费1秘密：不发现你所在
地点的一个线索，改为选择你的弃牌堆中1张[[道具]]卡牌并加入你的手牌，
或发现连接地点的一个线索。

简化说明：
- 引擎的调查成功直接结算基础发现后才发 CLUE_DISCOVERED（无"改为"窗口）；
  本实现在该事件做事后校正：返还本地点的线索，再结算所选效果
  （与寻找答案同模式）；
- 二选一简化为自动选择：优先取回弃牌堆顶的[[道具]]卡，无道具时改为在
  第一个有线索的连接地点发现线索；实例属性 next_mode（"item"/"clue"）
  与 next_pick（道具卡 id）可由会话层在检定前指定；
- 两个分支均不可用时（弃牌堆无道具且连接地点无线索）不触发、不消耗；
- 数据 JSON 中 uses 键为 "secretss"（上游笔误），读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


def _secrets(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class ProfessorWilliamWebb(CardImplementation):
    card_id = "professor_william_webb_lv0"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 会话层可在检定前指定分支/目标；None = 自动
        self.next_mode: str | None = None   # "item" | "clue"
        self.next_pick: str | None = None   # 弃牌堆中的道具卡 id

    def _ready(self, ctx) -> bool:
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        return inst.uses.get(_secrets(inst), 0) > 0

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def replace_discovery(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or not self._ready(ctx):
            return
        origin = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if origin is None or origin.location_id != inv.location_id:
            return  # 仅"在你所在地点成功调查"

        mode, item_card, conn = self._plan(ctx, inv, origin)
        if mode is None:
            return  # 两分支均不可用

        inst = ctx.game_state.get_card_instance(self.instance_id)
        inst.exhausted = True
        inst.uses[_secrets(inst)] -= 1

        # 返还本地点的基础发现
        origin.clues += 1
        inv.clues = max(0, inv.clues - 1)

        if mode == "item":
            inv.discard.remove(item_card)
            inv.hand.append(item_card)
            ctx.extra["webb_returned_item"] = item_card
            ctx.game_state.log_effect(
                f"🎓 韦伯教授：改为取回弃牌堆中的"
                f"【{ctx.game_state.card_name(item_card)}】")
        else:
            conn.clues -= 1
            inv.clues += 1
            ctx.extra["webb_connected_clue"] = conn.location_id
            ctx.game_state.log_effect(
                f"🎓 韦伯教授：改为在连接地点"
                f"【{ctx.game_state.card_name(conn.location_id)}】发现1条线索")

    def _plan(self, ctx, inv, origin):
        """返回 (mode, item_card_id, connecting_location)；不可用为 (None, …)。"""
        item = self._find_item(ctx, inv)
        conn = self._first_connecting_with_clues(ctx, origin)
        mode = self.next_mode
        if mode == "item" and item is None:
            mode = None
        elif mode == "clue" and conn is None:
            mode = None
        elif mode is None:
            mode = "item" if item is not None else ("clue" if conn is not None else None)
        self.next_mode = None
        self.next_pick = None
        return mode, item, conn

    def _find_item(self, ctx, inv) -> str | None:
        if self.next_pick is not None and self.next_pick in inv.discard:
            cd = ctx.game_state.get_card_data(self.next_pick)
            if self._is_item(cd):
                return self.next_pick
        for card_id in reversed(inv.discard):
            cd = ctx.game_state.get_card_data(card_id)
            if cd is not None and cd.type == CardType.ASSET:
                if self._is_item(cd):
                    return card_id
                break  # 只看弃牌堆顶最近的支援
        return None

    @staticmethod
    def _is_item(cd) -> bool:
        return (
            cd is not None
            and cd.type == CardType.ASSET
            and "item" in (cd.traits or [])
        )

    @staticmethod
    def _first_connecting_with_clues(ctx, origin):
        for conn_id in (origin.connections or []):
            conn = ctx.game_state.get_location(conn_id)
            if conn is not None and conn.clues > 0:
                return conn
        return None
