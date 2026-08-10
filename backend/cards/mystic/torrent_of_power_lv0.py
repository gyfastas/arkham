"""Torrent of Power (Level 0) — Mystic Skill. (03235)
将力量洪流投入技能检定时，从你控制的支援卡上花费最多3点充能作为额外费用。
每以此方式花费1点充能，力量洪流获得[willpower][wild]。

简化说明：
- 充能自动从你控制的带充能支援卡依次花费（无选择 UI；默认尽可能花满3点，
  取最大化成功率分支）。调用方可在 ctx.extra["charges_to_spend"] 指定数量
  （0 表示不花）。
- 图标结算：意志检定每充能+2（[willpower][wild]均生效），其他检定每充能+1
  （仅[wild]生效）；经 SKILL_TEST_COMMIT 的 ctx.amount 汇入投入图标总数
  （引擎回读为 committed_icons）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class TorrentOfPower(CardImplementation):
    card_id = "torrent_of_power_lv0"
    commit_effect_cost = 0
    commit_effect_label = "花费至多3充能：每充能+[willpower][wild]"

    @on_event(GameEvent.SKILL_TEST_COMMIT, priority=TimingPriority.WHEN)
    def spend_charges(self, ctx):
        if self.card_id not in (ctx.committed_cards or []):
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return

        budget = ctx.extra.get("charges_to_spend", 3)
        budget = max(0, min(3, int(budget)))
        spent = 0
        for iid in list(inv.play_area):
            if spent >= budget:
                break
            ci = ctx.game_state.get_card_instance(iid)
            if ci is None:
                continue
            available = ci.uses.get("charges", 0)
            if available <= 0:
                continue
            take = min(available, budget - spent)
            ci.uses["charges"] = available - take
            spent += take

        if spent <= 0:
            return
        per_charge = 2 if ctx.skill_type == Skill.WILLPOWER else 1
        ctx.modify_amount(spent * per_charge, "torrent_of_power_charges")
        ctx.extra["torrent_of_power_spent"] = spent
        ctx.game_state.log_effect(
            f"🌊 力量洪流：花费{spent}充能，投入图标+{spent * per_charge}")
