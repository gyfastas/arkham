"""Archaic Glyphs (Level 0) — Seeker Asset, Hand slot.
[行动]弃掉你手牌中1张含至少1个[intellect]技能图标的牌：
从供应堆拿取1资源放到古代雕文上，作为秘密。
强制 - 第3个秘密放到古代雕文上后：丢弃古代雕文并获得5资源。
在冒险日志中记录"你翻译出了雕文"。

简化说明：
- 弃牌目标默认为手牌中第一张含智力图标的牌（activate 可显式传 card_id）；
- "冒险日志"记录在 scenario.vars["campaign_log"]（与 Strange Solution 一致）。
"""

from backend.cards.base import CardImplementation
from backend.engine.slots import vacate_asset_slots

CAMPAIGN_LOG_ENTRY = "你翻译出了雕文"


class ArchaicGlyphs(CardImplementation):
    card_id = "archaic_glyphs_lv0"
    activations = [{
        "id": "translate",
        "label": "[行动]弃1张含智力图标的手牌：放置1个秘密",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 card_id: str | None = None) -> bool:
        """[行动]弃1张含智力图标的手牌：放置1个秘密；第3个秘密触发结算。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False

        if card_id is None:
            card_id = self._first_intellect_card(game_state, inv)
        if card_id is None or card_id not in inv.hand:
            return False
        cd = game_state.get_card_data(card_id)
        if cd is None or (cd.skill_icons or {}).get("intellect", 0) < 1:
            return False

        inv.hand.remove(card_id)
        inv.discard.append(card_id)
        secrets = inst.uses.get("secrets", 0) + 1
        inst.uses["secrets"] = secrets
        game_state.log_effect(
            f"📜 古代雕文：弃掉【{game_state.card_name(card_id)}】，"
            f"放置第{secrets}个秘密"
        )

        if secrets >= 3:
            self._translate_complete(game_state, inv)
        return True

    def _translate_complete(self, game_state, inv) -> None:
        """强制 - 第3个秘密：丢弃雕文、获得5资源、记录冒险日志。"""
        vacate_asset_slots(game_state, self.instance_id)
        if self.instance_id in inv.play_area:
            inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)
        inv.resources += 5
        log = game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY not in log:
            log.append(CAMPAIGN_LOG_ENTRY)
        game_state.log_effect("📜 古代雕文：翻译完成！丢弃雕文，获得5资源")

    @staticmethod
    def _first_intellect_card(game_state, inv) -> str | None:
        for cid in inv.hand:
            cd = game_state.get_card_data(cid)
            if cd is not None and (cd.skill_icons or {}).get("intellect", 0) >= 1:
                return cid
        return None
