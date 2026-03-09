"""Old Book of Lore (Level 3) — Seeker Asset, Hand slot.
升级版智慧古书：消耗行动搜索牌库顶3张，可花费秘密让目标立即打出(-2费用)。
"""

from backend.cards.base import CardImplementation


class OldBookOfLoreLv3(CardImplementation):
    card_id = "old_book_of_lore_lv3"
    # Skeleton — upgraded version with secrets and cost reduction
