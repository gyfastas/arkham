"""Shrewd Analysis (Level 0) — Seeker Asset (Permanent). (04106)
永久。每副牌组限制1张。
每当你升级带有(未鉴定)或(未翻译)副标题的卡牌时，你可以多升级1张该
卡牌，而不用花费经验值。如果你这么做，从可用选项中随机选择该卡牌的
2张升级版本。(你仍须满足牌组构建的所有要求。)

简化说明：
- 永久/升级规则属于战役模式的牌组管理，游戏内无事件效果（"永久"入场
  由构筑/会话层处理）；
- 提供公开方法 choose_upgrade_pair() 供战役层使用：从符合条件的升级
  选项中随机选取2个不同版本（选项不足2个时全取）；" Untranslated /
  Unidentified 副标题"判定提供 is_upgradeable_subtitle() 辅助。
"""

import random

from backend.cards.base import CardImplementation

_UNIDENTIFIED = "(unidentified)"
_UNTRANSLATED = "(untranslated)"


class ShrewdAnalysis(CardImplementation):
    card_id = "shrewd_analysis_lv0"

    @staticmethod
    def is_upgradeable_subtitle(subname: str | None) -> bool:
        """该副标题是否属于(未鉴定)/(未翻译)，可触发老练分析。"""
        if not subname:
            return False
        return subname.strip().lower() in (_UNIDENTIFIED, _UNTRANSLATED)

    @staticmethod
    def choose_upgrade_pair(eligible_options: list[str],
                            rng: random.Random | None = None) -> list[str]:
        """从符合条件的升级选项中随机选择2个不同版本（不足2个则全取）。"""
        options = list(dict.fromkeys(eligible_options))
        if len(options) <= 2:
            return options
        picker = rng if rng is not None else random
        return picker.sample(options, 2)
