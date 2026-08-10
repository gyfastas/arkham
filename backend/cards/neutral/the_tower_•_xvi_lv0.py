"""The Tower • XVI (Level 0) — Neutral Asset (Tarot), Basic Weakness.
只要高塔·XVI在你手牌中，你就不能投入卡牌到技能检定。
如果在设置阶段抽到（换牌前后），不能替换，必须留在起始手牌中。

简化说明：
- "不能投入卡牌"是投入窗口限制，由 can_commit_cards() 表达，供会话层在
  构建投入选项时查询（与 the_king_in_yellow_lv0 的 can_commit 同一缺口：
  引擎提交通道不做投入权限校验）。
- persistent_in_hand = True：抽到后保持在手牌中的注册，会话层可经
  registry.active_instances 查询该限制。
- 起始手牌/换牌限制属于设置阶段流程（game.setup 的 set-aside 通道），
  由会话/设置层负责，引擎缺口。
"""

from backend.cards.base import CardImplementation


class TheTowerXVI(CardImplementation):
    card_id = "the_tower_•_xvi_lv0"
    persistent_in_hand = True  # 手牌中持续生效的投入限制

    def can_commit_cards(self, game_state, investigator_id) -> bool:
        """高塔·XVI在手牌中时，不能投入任何卡牌到技能检定。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        if "the_tower_•_xvi_lv0" in inv.hand:
            return False
        return True

    def can_replace_in_opening_hand(self, game_state, investigator_id) -> bool:
        """官方：设置阶段抽到本卡时不能替换（由设置/会话层查询）。"""
        return False
