"""Dumb Luck (Level 0) — Survivor Event.
快速。在躲避一名非[[精英]]敌人的尝试中，你检定失败且低于难度2点以内后打出。
将该敌人放到遭遇牌堆顶。

简化说明：
- 从手牌自动打出（persistent_in_hand）：敏捷检定失败且差值≤2、资源足够、
  有交战的非精英敌人时自动支付2资源打出。
- 引擎的失败躲避不携带目标敌人信息（SKILL_TEST_FAILED 无 enemy 字段），
  目标简化为第一个与你交战的非精英敌人（官方为被躲避的那个敌人）。
- 不区分"躲避尝试"与其他敏捷检定（同 survival_instinct 的既有简化）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class DumbLuck(CardImplementation):
    card_id = "dumb_luck_lv0"
    persistent_in_hand = True  # 在手牌中持续监听躲避失败窗口

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def put_enemy_on_encounter_deck(self, ctx):
        if ctx.skill_type != Skill.AGILITY:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        margin = (ctx.difficulty or 0) - (ctx.modified_skill or 0)
        if margin < 1 or margin > 2:
            return
        cd = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(cd, "cost", 2) or 2) if cd else 2
        if inv.resources < cost:
            return

        # 目标：第一个与你交战的非精英敌人
        target_iid = None
        for iid in inv.threat_area:
            enemy = ctx.game_state.get_card_instance(iid)
            if enemy is None:
                continue
            enemy_cd = ctx.game_state.get_card_data(enemy.card_id)
            if enemy_cd is not None and not is_elite_enemy(enemy_cd):
                target_iid = iid
                break
        if target_iid is None:
            return

        # 自动打出
        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)

        # 将该敌人放到遭遇牌堆顶
        enemy = ctx.game_state.get_card_instance(target_iid)
        inv.threat_area.remove(target_iid)
        ctx.game_state.cards_in_play.pop(target_iid, None)
        ctx.game_state.scenario.encounter_deck.insert(0, enemy.card_id)
        ctx.extra["dumb_luck_topdecked"] = enemy.card_id
        ctx.game_state.log_effect(
            f"🍀 傻人有傻福：【{ctx.game_state.card_name(enemy.card_id)}】放到遭遇牌堆顶")
