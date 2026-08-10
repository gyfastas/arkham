"""Dream Diary (Level 0) — Seeker Asset, Hand slot. (06112)
[行动]：从你的绑定卡牌中查找梦的本质并加入你的手牌。
[反应]在你于投入了梦的本质的技能检定中以3点或更多差值成功后：在冒险日志
中记录"你已解读梦境"。

简化说明：
- 绑定卡池存于 scenario.vars["set_aside"]（与 essence_of_the_dream_lv0 /
  miss_doyle 同款约定）；本卡入场时若梦的本质不在任何区域，则补入绑定池；
- 梦的本质投入后回到绑定池由其自身实现处理（essence_of_the_dream_lv0）；
- 冒险日志记录在 scenario.vars["campaign_log"]。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

ESSENCE = "essence_of_the_dream_lv0"
CAMPAIGN_LOG_ENTRY = "你已解读梦境"
SET_ASIDE_VAR = "set_aside"


class DreamDiary(CardImplementation):
    card_id = "dream_diary_lv0"
    activations = [{
        "id": "fetch_essence",
        "label": "[行动]从绑定卡中查找梦的本质入手",
        "method": "activate",
        "actions": 1,
    }]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def ensure_bonded_pool(self, ctx):
        """入场：确保绑定池中有梦的本质（绑定卡开局即场外存放）。"""
        if ctx.target != self.instance_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        self._ensure_bonded(ctx.game_state, inv)

    def activate(self, game_state, investigator_id: str) -> bool:
        """[行动]：从绑定卡中查找梦的本质加入手牌。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        pool = game_state.scenario.vars.setdefault(SET_ASIDE_VAR, [])
        if ESSENCE not in pool:
            return False
        pool.remove(ESSENCE)
        inv.hand.append(ESSENCE)
        game_state.log_effect("📔 梦境日记：从绑定卡中找到【梦的本质】入手")
        return True

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def record_interpreted(self, ctx):
        """投入梦的本质且以3+差值成功：记录冒险日志。"""
        if ESSENCE not in (ctx.committed_cards or []):
            return
        if not self._owns(ctx.game_state, ctx.investigator_id):
            return
        margin = (ctx.modified_skill or 0) - (ctx.difficulty or 0)
        if margin < 3:
            return
        log = ctx.game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY not in log:
            log.append(CAMPAIGN_LOG_ENTRY)
        ctx.extra["dream_diary_interpreted"] = True
        ctx.game_state.log_effect("📔 梦境日记：解读梦境（3+差值成功），记录冒险日志")

    def _owns(self, game_state, investigator_id) -> bool:
        inv = game_state.get_investigator(investigator_id)
        return inv is not None and self.instance_id in inv.play_area

    @staticmethod
    def _ensure_bonded(game_state, inv) -> None:
        """梦的本质不在任何区域时：补入绑定池。"""
        zones = [inv.hand, inv.deck, inv.discard]
        pooled = (
            game_state.scenario.vars.get(SET_ASIDE_VAR, [])
            + game_state.scenario.vars.get("out_of_play", [])
        )
        in_play = any(
            (ci := game_state.get_card_instance(iid)) is not None
            and ci.card_id == ESSENCE
            for iid in inv.play_area
        )
        if in_play or any(ESSENCE in z for z in zones) or ESSENCE in pooled:
            return
        game_state.scenario.vars.setdefault(SET_ASIDE_VAR, []).append(ESSENCE)
