"""Professor William Webb (Level 2) — Seeker Asset, Ally slot. (08106)
使用(3秘密)。
[反应]在你成功调查时，消耗威廉·韦伯教授并花费1秘密：选择你的弃牌堆
中1张[[道具]]卡牌并加入你的手牌。你可以不发现你所在地点的一个线索，
改为发现连接地点的一个线索。

简化说明：
- 取回道具为必选项：弃牌堆没有[[道具]]卡时不触发（不消耗不横置）；
  目标简化为弃牌堆顶最近的道具卡（实例属性 next_pick 可指定）；
- "改为在连接地点发现线索"为可选项：默认不改为（保留本地点发现），
  实例属性 next_redirect=True 时改为在第一个有线索的连接地点发现
  （会话层在检定前设置；事后校正模式与 lv0 相同）；
- 数据 JSON 中 uses 键为 "secretss"（上游笔误），读取时兼容两种键名。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority


def _secrets(inst) -> str:
    return "secretss" if "secretss" in inst.uses else "secrets"


class ProfessorWilliamWebbLv2(CardImplementation):
    card_id = "professor_william_webb_lv2"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self.next_pick: str | None = None    # 弃牌堆中的道具卡 id
        self.next_redirect: bool = False     # True：改为在连接地点发现线索

    @on_event(GameEvent.CLUE_DISCOVERED, priority=TimingPriority.WHEN)
    def on_successful_investigate(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return
        if inst.uses.get(_secrets(inst), 0) <= 0:
            return
        origin = ctx.game_state.get_location(ctx.location_id or inv.location_id)
        if origin is None or origin.location_id != inv.location_id:
            return  # 仅"在你所在地点成功调查"

        item = self._find_item(ctx, inv)
        if item is None:
            return  # 必选分支不可用：不触发

        conn = None
        redirect = self.next_redirect
        if redirect:
            conn = self._first_connecting_with_clues(ctx, origin)
            if conn is None:
                redirect = False
        self.next_pick = None
        self.next_redirect = False

        inst.exhausted = True
        inst.uses[_secrets(inst)] -= 1

        # 必选项：道具入手
        inv.discard.remove(item)
        inv.hand.append(item)
        ctx.extra["webb_returned_item"] = item

        if redirect:
            # 可选项：本地点的发现改为连接地点（事后校正）
            origin.clues += 1
            inv.clues = max(0, inv.clues - 1)
            conn.clues -= 1
            inv.clues += 1
            ctx.extra["webb_connected_clue"] = conn.location_id
            ctx.game_state.log_effect(
                f"🎓 韦伯教授：取回【{ctx.game_state.card_name(item)}】，"
                f"改为在连接地点【{ctx.game_state.card_name(conn.location_id)}】发现线索")
        else:
            ctx.game_state.log_effect(
                f"🎓 韦伯教授：取回弃牌堆中的【{ctx.game_state.card_name(item)}】")

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
