"""The Council's Coffer (Level 2) — Neutral Asset. (05196)
使用（1[每名调查员]锁）。若议会的金库上没有锁，每名调查员检索其牌组或
弃牌堆中的任意一张卡并立即打出，不支付费用。放逐议会的金库。（每场战役
限一次。）
[action][action]：检定任意技能（5）。若你成功，移除1个锁。你所在地点的
任意调查员可以发动此能力。

简化说明：
- 锁数量在进场时按调查员人数初始化（数据 JSON 无 uses 字段）。
- 技能检定由会话层执行：activate_unlock() 记录待决状态（2行动由会话层
  扣除），会话层以难度5跑任意技能检定（source 传本卡实例），
  SKILL_TEST_SUCCESSFUL 时移除1锁。
- 锁清零的奖励：每名调查员自动检索其弃牌堆顶（其次牌堆顶）的第一张卡并
  免费放入其play_area（官方为玩家任选卡牌；资源不扣）。卡牌能力的注册/
  激活需会话层接线（同 calling_in_favors_lv0 的说明）。
- 放逐登记 scenario.vars["exiled_cards"]（devils_luck_lv1 惯例）；
  "每场战役限一次"登记 scenario.vars["councils_coffer_used"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import CardType, GameEvent, TimingPriority
from backend.models.state import CardInstance


class TheCouncilsCoffer(CardImplementation):
    card_id = "the_councils_coffer_lv2"
    activations = [{
        "id": "unlock",
        "label": "[行动×2] 检定任意技能(5)：移除1个锁",
        "method": "activate_unlock",
        "actions": 2,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._pending_unlock: str | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def init_locks(self, ctx):
        """进场：放置 1锁/每名调查员。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        n = max(1, len(ctx.game_state.investigators))
        inst.uses["locks"] = n

    def activate_unlock(self, game_state, investigator_id) -> bool:
        """[action][action]：记录一次开锁检定（会话层随后跑难度5的检定）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if inst.uses.get("locks", 0) <= 0:
            return False
        # "你所在地点的任意调查员"：需与本卡持有者在同一地点
        owner = game_state.get_investigator(inst.controller_id)
        if owner is not None and inv.location_id != owner.location_id:
            return False
        self._pending_unlock = investigator_id
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def remove_lock(self, ctx):
        """开锁检定成功：移除1个锁；锁清零触发检索奖励并放逐。"""
        if self._pending_unlock is None:
            return
        if ctx.investigator_id != self._pending_unlock:
            return
        self._pending_unlock = None
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        locks = inst.uses.get("locks", 0)
        if locks <= 0:
            return
        inst.uses["locks"] = locks - 1
        ctx.extra["councils_coffer_lock_removed"] = True
        if inst.uses["locks"] == 0:
            self._pay_off(ctx.game_state)

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def clear_pending(self, ctx):
        if self._pending_unlock == ctx.investigator_id:
            self._pending_unlock = None

    def _pay_off(self, game_state) -> None:
        """锁清零：每名调查员免费打出检索到的一张卡，放逐本卡。"""
        scenario = game_state.scenario
        if scenario.vars.get("councils_coffer_used"):
            return  # 每场战役限一次
        scenario.vars["councils_coffer_used"] = True

        played = {}
        for inv in game_state.investigators.values():
            # 简化：自动检索弃牌堆顶起、继而牌堆顶起的第一张支援卡免费打出
            # （官方为任选任意卡牌；事件/技能的"打出即结算"不在此通道内）
            cid = None
            for candidate in list(reversed(inv.discard)) + list(inv.deck):
                cd = game_state.get_card_data(candidate)
                if cd is not None and cd.type == CardType.ASSET:
                    cid = candidate
                    break
            if cid is None:
                continue
            cd = game_state.get_card_data(cid)
            if cid in inv.discard:
                inv.discard.remove(cid)
            elif cid in inv.deck:
                inv.deck.remove(cid)
            inst_id = game_state.next_instance_id()
            ci = CardInstance(
                instance_id=inst_id,
                card_id=cid,
                owner_id=inv.investigator_id,
                controller_id=inv.investigator_id,
                slot_used=list(getattr(cd, "slots", []) or []),
            )
            if getattr(cd, "uses", None):
                ci.uses = dict(cd.uses)
            game_state.cards_in_play[inst_id] = ci
            inv.play_area.append(inst_id)
            played[inv.investigator_id] = cid

        # 放逐本卡
        inst = game_state.get_card_instance(self.instance_id)
        if inst is not None:
            owner = game_state.get_investigator(inst.controller_id)
            if owner is not None and self.instance_id in owner.play_area:
                owner.play_area.remove(self.instance_id)
            game_state.cards_in_play.pop(self.instance_id, None)
        scenario.vars.setdefault("exiled_cards", []).append("the_councils_coffer_lv2")
        scenario.vars["councils_coffer_played"] = played
