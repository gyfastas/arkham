"""Ariadne's Twine (Level 3) — Seeker Asset, Arcane slot. (07304)
使用(0秘密)。
阿里阿德涅之线上的秘密可以视为在你所在地点任一调查员控制的任一资产上
来花费。
[快速]横置阿里阿德涅之线：将你控制的一张资产上的1个秘密移动到你的资源池，
作为1个资源，或反之亦然。

简化说明：
- "线上的秘密可视为任一资产上的秘密来花费"是跨卡花费重定向：其它资产的
  能力各自检查自身 uses，引擎无统一花费钩子——引擎缺口，见报告；
- [快速]能力的两个方向由 direction 指定（"to_resource" 秘密→资源，缺省；
  "to_secret" 资源→秘密）；资产缺省为本卡（秘密→资源时若本卡无秘密，则取
  你控制的第一张带秘密的资产；官方为玩家自选资产）；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_count, uses_key, uses_spend


class AriadnesTwine(CardImplementation):
    card_id = "ariadnes_twine_lv3"
    activations = [{
        "id": "convert",
        "label": "[快速]横置：1秘密换1资源，或反之",
        "method": "activate",
    }]

    def activate(self, game_state, investigator_id: str,
                 direction: str = "to_resource",
                 asset_instance_id: str | None = None) -> bool:
        """[快速]横置：资产上1秘密→资源池1资源，或资源池1资源→资产上1秘密。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        if direction == "to_resource":
            source = self._find_secret_source(game_state, inv,
                                              asset_instance_id)
            if source is None:
                return False
            inst.exhausted = True
            uses_spend(source, "secrets")
            inv.resources += 1
            game_state.log_effect(
                f"🧵 阿里阿德涅之线：横置，"
                f"【{game_state.card_name(source.card_id)}】上1秘密转为1资源"
            )
            return True
        if direction == "to_secret":
            target = self._resolve_asset(game_state, inv, asset_instance_id)
            if target is None or inv.resources < 1:
                return False
            inst.exhausted = True
            inv.resources -= 1
            key = uses_key(target, "secrets")
            target.uses[key] = target.uses.get(key, 0) + 1
            game_state.log_effect(
                f"🧵 阿里阿德涅之线：横置，1资源转为"
                f"【{game_state.card_name(target.card_id)}】上1秘密"
            )
            return True
        return False

    def _resolve_asset(self, game_state, inv, instance_id):
        """你控制的资产（缺省本卡）。"""
        if instance_id is None:
            return game_state.get_card_instance(self.instance_id)
        if instance_id not in inv.play_area:
            return None
        return game_state.get_card_instance(instance_id)

    def _find_secret_source(self, game_state, inv, instance_id):
        """秘密来源资产：显式指定 > 本卡 > 你控制的第一张带秘密的资产。"""
        if instance_id is not None:
            if instance_id not in inv.play_area:
                return None
            ci = game_state.get_card_instance(instance_id)
            return ci if ci is not None and uses_count(ci, "secrets") > 0 else None
        own = game_state.get_card_instance(self.instance_id)
        if own is not None and uses_count(own, "secrets") > 0:
            return own
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            if ci is not None and uses_count(ci, "secrets") > 0:
                return ci
        return None
