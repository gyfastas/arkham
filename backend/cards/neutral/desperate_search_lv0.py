"""Desperate Search (Level 0) — Neutral Skill (Desperate).
4个智力图标由 skill_icons 数据经提交流程自动结算。
仅当你剩余神智值≤3时才可投入技能检定。每次检定最多投入1张。

简化说明：同 say_your_prayers_lv0（can_commit 未接入引擎提交窗口）。
"""

from backend.cards.base import CardImplementation


class DesperateSearch(CardImplementation):
    card_id = "desperate_search_lv0"

    def can_commit(self, game_state, investigator_id: str) -> bool:
        """官方投入限制：仅当你剩余神智值≤3时可投入本卡。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        return inv.remaining_sanity <= 3
