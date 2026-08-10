"""Venturer (Level 0) — Guardian Asset, Ally slot. (04018)
使用(3补给)。
[快速]花费1补给并消耗冒险家：将1补给或弹药放在你所在地点的一位调查员
控制的一张支援卡上。

简化说明：
- 快速激活（activations 声明，actions=0）：activate() 消耗1补给并横置。
- 目标：可用 target_instance_id 指定同地点调查员控制的支援；默认选同地点
  第一张卡面带弹药/补给用途的支援（自己优先；跳过冒险家本身，除非没有
  其他合法目标——官方允许以自身为目标，但无意义时优先他选）。
- token_type 可为 "ammo"/"supplies"；缺省按目标卡面 uses 键自动选择
  （优先弹药）。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import CardType


class Venturer(CardImplementation):
    card_id = "venturer_lv0"
    activations = [{
        "id": "place_token",
        "label": "花1补给并横置：在同地点一张支援上放1补给/弹药",
        "method": "activate",
        "actions": 0,
    }]

    def activate(self, game_state, investigator_id: str,
                 target_instance_id: str | None = None,
                 token_type: str | None = None) -> bool:
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if inst.exhausted:
            return False
        # 数据容错：历史数据曾把 uses 键误写为 "suppliess"
        if "supplies" not in inst.uses and "suppliess" in inst.uses:
            inst.uses["supplies"] = inst.uses.pop("suppliess")
        if inst.uses.get("supplies", 0) <= 0:
            return False

        target = self._choose_target(game_state, inv, target_instance_id)
        if target is None:
            return False
        token = token_type or self._default_token(game_state, target)
        if token not in ("ammo", "supplies"):
            return False

        inst.uses["supplies"] -= 1
        inst.exhausted = True
        target.uses[token] = target.uses.get(token, 0) + 1
        game_state.log_effect(
            f"🧭 冒险家：消耗1补给并横置，在【{game_state.card_name(target.card_id)}】"
            f"上放置1{'弹药' if token == 'ammo' else '补给'}")
        return True

    def _choose_target(self, game_state, inv, target_instance_id):
        """同地点调查员（自己优先）控制的支援；须卡面带弹药/补给用途。"""
        def usable(iid: str):
            ci = game_state.get_card_instance(iid)
            if ci is None:
                return None
            cd = game_state.get_card_data(ci.card_id)
            if cd is None or cd.type != CardType.ASSET:
                return None
            uses = cd.uses or {}
            if not any(k in uses for k in ("ammo", "supplies", "suppliess")):
                return None
            return ci

        if target_instance_id is not None:
            ci = game_state.get_card_instance(target_instance_id)
            if ci is None:
                return None
            holder = game_state.get_investigator(ci.controller_id)
            if (holder is None or holder.location_id != inv.location_id
                    or target_instance_id not in holder.play_area):
                return None
            return ci  # 显式目标不强制要求卡面带用途（尊重会话层选择）

        investigators = [inv] + [
            other for other in game_state.get_investigators_at_location(
                inv.location_id)
            if other.investigator_id != inv.investigator_id
        ]
        fallback = None
        for other in investigators:
            for iid in other.play_area:
                ci = usable(iid)
                if ci is None:
                    continue
                if iid == self.instance_id:
                    fallback = fallback or ci  # 自身仅作兜底
                    continue
                return ci
        return fallback

    @staticmethod
    def _default_token(game_state, target) -> str:
        cd = game_state.get_card_data(target.card_id)
        uses = (cd.uses or {}) if cd else {}
        if "ammo" in uses:
            return "ammo"
        return "supplies"
