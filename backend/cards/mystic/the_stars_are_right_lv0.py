"""The Stars Are Right (Level 0) — Mystic Event, bonded (Stargazing). (06028)
绑定(仰望星空)。
显现 - 将本卡移出游戏。选择一位调查员。该调查员抽1张牌，获得1资源，并可以
立即进行一个行动，如同在其回合中（该行动不计入每回合行动数）。

简化/缺口说明：
- 本卡经仰望星空进入遭遇牌堆；引擎不会在抽出遭遇牌时注册玩家卡实现
  （引擎缺口），生产接线需会话层在抽出时激活本实现。
- 显现经 ENCOUNTER_CARD_DRAWN 触发：立即结算（移出游戏 + 抽牌 + 资源 +
  行动），并标记 scenario.vars["cancelled_encounter"] 使会话层跳过常规
  显现结算（同 ward_of_protection 惯例）。phase_mythos 随后仍会将其送入
  遭遇弃牌堆，ROUND_BEGINS 时按 removed_from_game 登记剔除。
- "选择一位调查员"自动选抽牌者本人；"立即行动"近似为 actions_remaining +1
  （真正的回合外立即行动需要会话层窗口，引擎缺口）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class TheStarsAreRight(CardImplementation):
    card_id = "the_stars_are_right_lv0"

    @on_event(GameEvent.ENCOUNTER_CARD_DRAWN, priority=TimingPriority.WHEN)
    def revelation(self, ctx):
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        # 抽1张牌（直接牌堆顶抽取，同 lucky_lv0 的抽牌近似）
        if inv.deck:
            inv.hand.append(inv.deck.pop(0))
        inv.resources += 1
        inv.actions_remaining += 1  # 立即行动的近似（见 docstring）
        scen = ctx.game_state.scenario
        scen.vars.setdefault("removed_from_game", []).append(self.card_id)
        scen.vars["cancelled_encounter"] = self.card_id
        ctx.extra["stars_are_right_chosen"] = inv.investigator_id
        ctx.game_state.log_effect(
            f"🌟 群星正确之时：【{ctx.game_state.card_name(inv.investigator_id)}】"
            "抽1张牌、获得1资源、+1行动；本卡移出游戏")

    @on_event(GameEvent.ROUND_BEGINS, priority=TimingPriority.AFTER)
    def strip_from_encounter_discard(self, ctx):
        """移出游戏的卡不应留在遭遇弃牌堆（phase_mythos 会无条件送入）。"""
        scen = ctx.game_state.scenario
        if self.card_id not in scen.vars.get("removed_from_game", []):
            return
        while self.card_id in scen.encounter_discard:
            scen.encounter_discard.remove(self.card_id)
