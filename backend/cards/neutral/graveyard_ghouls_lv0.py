"""Graveyard Ghouls (Level 0) — Neutral Enemy, Signature Weakness (William Yorick).
猎物 - 仅限威廉·约里克。猎手。
墓地食尸鬼与你交战时，你弃牌堆中的卡牌不能离开弃牌堆。

简化说明：
- 敌人数据（战斗3/生命3/躲避2/伤害1/恐惧1，猎手关键词）不在玩家卡 JSON
  加载通道内（server.game_session._load_player_cards 不映射 enemy_* / keywords
  字段）——需要会话/数据层接线；测试以 make_enemy_data 注入。
- "猎物：仅限约里克"影响生成时的交战对象选择，引擎生成通道未接入，暂由
  会话层负责。
- "弃牌堆锁定"没有通用的弃牌堆出口钩子，由 can_leave_discard() 表达，
  供会话层在会从弃牌堆取牌的效果（如 Scavenging）处查询。
"""

from backend.cards.base import CardImplementation


class GraveyardGhouls(CardImplementation):
    card_id = "graveyard_ghouls_lv0"

    def can_leave_discard(self, game_state, investigator_id) -> bool:
        """与你交战时，你弃牌堆中的卡牌不能离开弃牌堆。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return True
        for inst_id in inv.threat_area:
            inst = game_state.get_card_instance(inst_id)
            if inst is not None and inst.card_id == "graveyard_ghouls_lv0":
                return False
        return True
