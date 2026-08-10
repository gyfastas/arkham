"""The Eye of Truth (Level 5) — Seeker Skill. (06325)
如果这次技能检定是诡计卡上的检定，且检定成功，将该诡计卡加入胜利牌区，
并叠加真理之眼到其上。
只要真理之眼叠加到诡计卡，其技能图标会投入到该卡牌的同名卡牌的所有
技能检定。

简化说明：
- 引擎的检定上下文没有"本次检定来自诡计卡"的标记（引擎缺口，见报告）。
  会话/剧本层在发起诡计卡检定前调用 mark_treachery_test(game_state, id)
  写入 scenario.vars（引擎在投入时新建的临时实现实例也能读到）；检定
  成功后将该诡计卡加入胜利牌区，本卡改为叠加其上（离开弃牌流程，
  记录在 scenario.vars["eye_of_truth_attached"]）；
- 叠加期间"图标投入到同名诡计卡的所有检定"需要持续注册的效果入口，
  而投入技能的临时实现在检定结束即被引擎注销（引擎缺口）；提供
  attached_icons(game_state, treachery_card_id) 供会话层查询补加（固定
  4个 wild 图标，即 +4）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

_ATTACHED = "eye_of_truth_attached"
_CURRENT_TEST = "eye_of_truth_current_test"


class TheEyeOfTruth(CardImplementation):
    card_id = "the_eye_of_truth_lv5"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._attach_pending = False

    @staticmethod
    def mark_treachery_test(game_state, treachery_card_id: str) -> None:
        """会话/剧本层：声明当前技能检定来自该诡计卡上的能力。"""
        game_state.scenario.vars[_CURRENT_TEST] = treachery_card_id

    @staticmethod
    def attached_icons(game_state, treachery_card_id: str) -> int:
        """叠加期间：对同名诡计卡检定贡献的图标数（4个wild → +4）。"""
        attached = game_state.scenario.vars.get(_ATTACHED) or {}
        return 4 if attached.get("treachery_card_id") == treachery_card_id else 0

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def attach_on_treachery_success(self, ctx):
        """诡计卡上的检定成功：该诡计卡入胜利牌区，本卡叠加其上。"""
        treachery = ctx.game_state.scenario.vars.get(_CURRENT_TEST)
        if self.card_id not in ctx.committed_cards or not treachery:
            return
        ctx.game_state.scenario.victory_display.append(treachery)
        ctx.game_state.scenario.vars[_ATTACHED] = {
            "treachery_card_id": treachery,
            "owner_id": ctx.investigator_id,
        }
        self._attach_pending = True
        ctx.extra["eye_of_truth_attached"] = treachery
        ctx.game_state.log_effect(
            f"👁️ 真理之眼：【{ctx.game_state.card_name(treachery)}】"
            "加入胜利牌区，真理之眼叠加其上"
        )

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def leave_play_attached(self, ctx):
        """叠加后本卡不进弃牌堆（引擎已在 ST.8 将其弃置，此处捞出场外）。"""
        if self._attach_pending:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is not None and self.card_id in inv.discard:
                inv.discard.remove(self.card_id)
        self._attach_pending = False
        ctx.game_state.scenario.vars.pop(_CURRENT_TEST, None)
