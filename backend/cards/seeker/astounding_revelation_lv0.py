"""Astounding Revelation (Level 0) — Seeker Event. (06023)
无数。惊人启示无法被打出。
[反应]当你检索你的牌堆且惊人启示在被检索的卡牌中时，丢弃它：获得2资源，
或在你控制的一张资产上放置1个秘密。（每次检索限一个[[研究]]能力。）

简化说明：
- 引擎无"检索牌堆"事件（现有检索效果均直接操作牌堆），本卡效果实现为公开
  方法 on_searched()，由检索效果/会话层在检索时传入被检索的卡表——引擎
  缺口（需 DECK_SEARCHED 钩子），见报告；
- "获得2资源或放置1秘密"由 choose 指定（缺省获得2资源）；放置秘密的目标
  资产缺省为你控制的第一张带 uses 的资产；
- "每次检索限一个研究能力"需由检索方在单次检索内去重（引擎缺口同上）。
"""

from backend.cards.base import CardImplementation


class AstoundingRevelation(CardImplementation):
    card_id = "astounding_revelation_lv0"

    def on_searched(self, game_state, investigator_id: str,
                    searched_cards: list[str],
                    choose: str = "resources",
                    target_instance_id: str | None = None) -> bool:
        """检索牌堆时若本卡在被检索卡中：丢弃它，获得2资源或放置1秘密。"""
        if self.card_id not in (searched_cards or []):
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.card_id not in inv.deck:
            return False

        inv.deck.remove(self.card_id)
        inv.discard.append(self.card_id)

        if choose == "secret":
            target = self._resolve_secret_target(game_state, inv,
                                                 target_instance_id)
            if target is not None:
                key = "secrets" if "secrets" in target.uses else (
                    next(iter(target.uses), "secrets"))
                target.uses[key] = target.uses.get(key, 0) + 1
                game_state.log_effect(
                    f"💡 惊人启示：检索中丢弃，"
                    f"在【{game_state.card_name(target.card_id)}】上放置1秘密"
                )
                return True
            # 无可放置秘密的资产：回退为获得资源
        inv.resources += 2
        game_state.log_effect("💡 惊人启示：检索中丢弃，获得2资源")
        return True

    def _resolve_secret_target(self, game_state, inv, instance_id):
        if instance_id is not None:
            if instance_id not in inv.play_area:
                return None
            return game_state.get_card_instance(instance_id)
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            if ci is not None and ci.uses:
                return ci
        return None
