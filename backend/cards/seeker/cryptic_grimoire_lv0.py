"""Cryptic Grimoire (Level 0) — Seeker Asset, Hand slot. (07022)
[行动]：向混沌袋中添加1个[诅咒]标记。
[行动]若混沌袋中有10个[诅咒]标记，丢弃神秘魔典：在冒险日志中记录
"你已译出神秘魔典"。将混沌袋中的5个[诅咒]标记替换为5个[祝福]标记。

简化说明：
- 混沌袋经 bind_chaos_bag 注入（registry.activate_card 生产环境自动接线；
  测试中手动绑定）；
- 冒险日志记录在 scenario.vars["campaign_log"]。
"""

from backend.cards.base import CardImplementation
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import ChaosTokenType

CAMPAIGN_LOG_ENTRY = "你已译出神秘魔典"
CURSE_THRESHOLD = 10
REPLACE_COUNT = 5


class CrypticGrimoire(CardImplementation):
    card_id = "cryptic_grimoire_lv0"
    activations = [
        {"id": "add_curse", "label": "[行动]向混沌袋添加1个[诅咒]标记",
         "method": "activate_curse", "actions": 1},
        {"id": "translate", "label": "[行动]（10诅咒）丢弃本卡：5诅咒换5祝福",
         "method": "activate_translate", "actions": 1},
    ]

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._bag = chaos_bag

    def activate_curse(self, game_state, investigator_id: str) -> bool:
        """[行动]：向混沌袋中添加1个[诅咒]标记。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        bag = getattr(self, "_bag", None)
        if bag is None:
            return False
        bag.add_token(ChaosTokenType.CURSE)
        game_state.log_effect("📖 神秘魔典：向混沌袋添加1个[诅咒]标记")
        return True

    def activate_translate(self, game_state, investigator_id: str) -> bool:
        """[行动]（袋中≥10诅咒）：丢弃本卡，5诅咒换5祝福，记录冒险日志。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        bag = getattr(self, "_bag", None)
        if bag is None:
            return False
        curses = sum(1 for t in bag.tokens if t == ChaosTokenType.CURSE)
        if curses < CURSE_THRESHOLD:
            return False

        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)

        for _ in range(REPLACE_COUNT):
            bag.remove(ChaosTokenType.CURSE)
            bag.add_token(ChaosTokenType.BLESS)

        log = game_state.scenario.vars.setdefault("campaign_log", [])
        if CAMPAIGN_LOG_ENTRY not in log:
            log.append(CAMPAIGN_LOG_ENTRY)
        game_state.log_effect(
            "📖 神秘魔典：译出完成！丢弃本卡，5个[诅咒]替换为5个[祝福]"
        )
        return True
