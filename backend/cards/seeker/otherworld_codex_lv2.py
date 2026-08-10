"""Otherworld Codex (Level 2) — Seeker Asset, Hand slot. (06158)
使用(3秘密)。[行动]消耗异界手稿并花费1秘密：在遭遇牌堆顶部9张卡牌中
查找并从中选择一张非[[精英]]卡牌。丢弃场上一张与所选卡牌同名的卡牌。
将所有查找的卡牌混洗回遭遇牌堆。

简化说明：
- 目标自动选择：遭遇牌堆顶9张中第一张"非精英且场上有同名卡"的卡牌
  （官方为玩家自选）；可用 activate(choose_card_id=...) 指定（仅查找
  范围内的非精英卡）；可用 activate(discard_instance_id=...) 指定丢弃的
  场上副本（默认同名第一张）；
- 场上副本的丢弃不经击败流程（不发 ENEMY_DEFEATED、不进胜利牌堆），
  直接离场入遭遇弃牌堆；
- 查找的9张混洗回遭遇牌堆（实现为整叠遭遇牌堆洗牌后回置，等效）；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

import random

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_spend


class OtherworldCodex(CardImplementation):
    card_id = "otherworld_codex_lv2"
    activations = [{
        "id": "purge",
        "label": "[行动]消耗+1秘密：查遭遇牌堆顶9张，丢弃场上同名非精英卡",
        "method": "activate",
        "actions": 1,
    }]

    def activate(self, game_state, investigator_id: str,
                 choose_card_id: str | None = None,
                 discard_instance_id: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False
        scenario = game_state.scenario
        if not scenario.encounter_deck:
            return False

        searched = list(scenario.encounter_deck[:9])
        if choose_card_id is not None:
            if choose_card_id not in searched or self._is_elite(game_state, choose_card_id):
                return False
            if discard_instance_id is None and \
                    self._find_in_play_copy(game_state, choose_card_id) is None:
                return False  # 显式选择必须能完成丢弃
            chosen = choose_card_id
        else:
            chosen = None
            for cid in searched:
                if self._is_elite(game_state, cid):
                    continue
                if self._find_in_play_copy(game_state, cid) is not None:
                    chosen = cid
                    break

        # 费用先行：消耗 + 花费1秘密（激活即支付，无论查找结果）
        if not uses_spend(inst, "secrets"):
            return False
        inst.exhausted = True

        if chosen is None:
            # 没有可用目标：仍完成查找并洗回（无丢弃）
            random.shuffle(scenario.encounter_deck)
            game_state.log_effect("🌐 异界手稿：顶9张中没有可丢弃的非精英卡，洗回遭遇牌堆")
            return True

        target_iid = discard_instance_id or self._find_in_play_copy(game_state, chosen)
        if target_iid is None:
            return False

        self._discard_from_play(game_state, target_iid)
        random.shuffle(scenario.encounter_deck)
        game_state.log_effect(
            f"🌐 异界手稿：丢弃场上1张【{game_state.card_name(chosen)}】，"
            "查找的卡牌混洗回遭遇牌堆"
        )
        return True

    @staticmethod
    def _is_elite(game_state, card_id: str) -> bool:
        cd = game_state.get_card_data(card_id)
        return cd is not None and "elite" in (cd.keywords or [])

    @staticmethod
    def _find_in_play_copy(game_state, card_id: str) -> str | None:
        for iid, inst in game_state.cards_in_play.items():
            if inst.card_id == card_id:
                return iid
        return None

    @staticmethod
    def _discard_from_play(game_state, instance_id: str) -> None:
        """场上副本直接离场入遭遇弃牌堆（非击败：无胜利结算）。"""
        inst = game_state.cards_in_play.pop(instance_id, None)
        if inst is None:
            return
        for inv in game_state.investigators.values():
            if instance_id in inv.threat_area:
                inv.threat_area.remove(instance_id)
            if instance_id in inv.play_area:
                inv.play_area.remove(instance_id)
        for loc in game_state.locations.values():
            if instance_id in loc.enemies:
                loc.enemies.remove(instance_id)
        game_state.scenario.encounter_discard.append(inst.card_id)
