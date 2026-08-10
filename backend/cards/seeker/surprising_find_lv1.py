"""Surprising Find (Level 1) — Seeker Skill. (06278)
多重。
[反应]在你查找你的牌堆时若惊喜的发现在被查找卡牌中：将其放置入你的
游戏区域。你必须将其投入到你执行的下一次能将其投入的技能检定。如果
该检定成功，抽1张牌。(每次查找最多使用一次[[研究]]能力。)

简化说明：
- 引擎的检索效果（如翻箱倒柜）没有"被检索到"事件（引擎缺口）；由
  检索方/会话层在检索到本卡时调用 on_searched() 完成放置入场。
- 入场为无槽位的临时 CardInstance；你执行的下一次技能检定自动投入
  （+1 wild 图标，官方为强制投入，故自动）；检定成功抽1张牌；
  检定结束本卡离场入弃牌堆。
- "每次查找最多一次[[研究]]能力"由检索方控制（一次检索只调用一张
  Research 卡的 on_searched）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.models.state import CardInstance


class SurprisingFind(CardImplementation):
    card_id = "surprising_find_lv1"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False      # 已入场、等待强制投入下一次检定
        self._committed = False  # 已投入本次检定
        self._play_instance: str | None = None

    def on_searched(self, game_state, investigator_id: str) -> bool:
        """[反应]被检索到时：从牌堆放置入你的游戏区域，待投入下次检定。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.deck:
            return False
        inv.deck.remove(self.card_id)
        iid = game_state.next_instance_id()
        inst = CardInstance(
            instance_id=iid, card_id=self.card_id,
            owner_id=investigator_id, controller_id=investigator_id,
        )
        game_state.cards_in_play[iid] = inst
        inv.play_area.append(iid)
        self._play_instance = iid
        self._armed = True
        game_state.log_effect("🔎 惊喜的发现：检索到，放置入游戏区域，须投入下次检定")
        return True

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def force_commit(self, ctx):
        """你执行的下一次检定自动投入：+1 wild 图标。"""
        if not self._armed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self._play_instance not in inv.play_area:
            return
        ctx.modify_amount(1, "surprising_find_icons")
        ctx.extra["surprising_find_committed"] = True
        self._armed = False
        self._committed = True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def draw_on_success(self, ctx):
        """投入的检定成功：抽1张牌。"""
        if not self._committed:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None and inv.deck:
            inv.hand.append(inv.deck.pop(0))
            ctx.extra["surprising_find_drew"] = True
            ctx.game_state.log_effect("🔎 惊喜的发现：检定成功，抽1张牌")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def leave_play(self, ctx):
        """检定结束：本卡离场入弃牌堆。"""
        iid = self._play_instance
        if iid is None:
            return
        inst = ctx.game_state.get_card_instance(iid)
        if inst is not None:
            inv = ctx.game_state.get_investigator(inst.owner_id)
            if inv is not None and iid in inv.play_area:
                inv.play_area.remove(iid)
                inv.discard.append(self.card_id)
            ctx.game_state.cards_in_play.pop(iid, None)
        self._play_instance = None
        self._armed = False
        self._committed = False
