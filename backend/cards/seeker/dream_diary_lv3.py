"""Dream Diary (Level 3) — Seeker Asset, Hand slot. (06238)
已研究。
当你的手牌不少于8张时，你的梦的本质获得[wild][wild]。
[反应]当你的回合开始时：从你的绑定卡牌中查找梦的本质并加入你的手牌。

简化说明：
- "已研究"的战役日志门槛由构筑层校验；
- 绑定卡池约定与 dream_diary_lv0 相同（scenario.vars["set_aside"]，
  入场时确保梦的本质在池中）；
- 回合开始反应自动触发（官方为必发反应）；
- "梦的本质获得[wild][wild]"在 SKILL_TEST_COMMIT 结算：本卡在场、你手牌
  ≥8张且梦的本质被投入时，本次检定+2图标（梦的本质本身无此能力的注册
  入口，由日记代为结算——仅当日记在场时生效）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

from backend.cards.seeker.dream_diary_lv0 import ESSENCE, SET_ASIDE_VAR, DreamDiary

HAND_THRESHOLD = 8
BONUS_ICONS = 2


class DreamDiaryLv3(CardImplementation):
    card_id = "dream_diary_lv3"

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def ensure_bonded_pool(self, ctx):
        """入场：确保绑定池中有梦的本质。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        DreamDiary._ensure_bonded(ctx.game_state, inv)

    @on_event(GameEvent.INVESTIGATOR_TURN_BEGINS, priority=TimingPriority.AFTER)
    def fetch_essence(self, ctx):
        """你的回合开始时：从绑定卡中查找梦的本质入手。"""
        if not self._owns(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        pool = ctx.game_state.scenario.vars.setdefault(SET_ASIDE_VAR, [])
        if ESSENCE not in pool:
            return
        pool.remove(ESSENCE)
        inv.hand.append(ESSENCE)
        ctx.game_state.log_effect("📔 梦境日记(3)：回合开始，【梦的本质】入手")

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def essence_wild_icons(self, ctx):
        """8+手牌时，投入的梦的本质额外+2图标。"""
        if ESSENCE not in (ctx.committed_cards or []):
            return
        if not self._owns(ctx.game_state, ctx.investigator_id):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or len(inv.hand) < HAND_THRESHOLD:
            return
        ctx.modify_amount(BONUS_ICONS, "dream_diary_lv3_essence")
        ctx.extra["dream_diary_lv3_wild"] = True

    def _owns(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area
