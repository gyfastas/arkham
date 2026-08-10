"""Schoffner's Catalogue (Level 0) — Survivor Asset. (08072)
Uses (5 secrets). If Schoffner's Catalogue has no secrets, discard it.
You may spend secrets on Schoffner's Catalogue as resources to pay for
[Item] assets played by any investigator at your location.

简化说明：
- 秘密代付实现为启动能力（activations 声明，0行动）：spend_for_item()
  花费 N 个秘密并将 N 资源交给目标调查员（官方为直接以秘密抵付道具
  费用；引擎的打出流程只认资源池，故先转换为资源——转换后未限定只能
  付道具，从简）。
- 秘密耗尽即弃置（含槽位释放与弃牌，内联结算）。
- 数据 uses 键为 "secretss"（复数化数据 artifact），按前缀 "secret" 兼容。
"""

from backend.cards.base import CardImplementation
from backend.engine.slots import vacate_asset_slots


class SchoffnersCatalogue(CardImplementation):
    card_id = "schoffners_catalogue_lv0"
    activations = [{
        "id": "spend_for_item",
        "label": "花N秘密：为当地点调查员的道具代付N资源",
        "method": "spend_for_item",
        "actions": 0,
    }]

    @staticmethod
    def _secrets(inst) -> str | None:
        """uses 中的秘密键（兼容数据复数化拼写）。"""
        for key in inst.uses:
            if key.startswith("secret"):
                return key
        return None

    def spend_for_item(self, game_state, investigator_id: str,
                       amount: int = 1) -> bool:
        """花费 amount 个秘密：给目标调查员 amount 资源（代付道具）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or amount < 1:
            return False
        # 目录持有者与目标须在同一地点
        holder = None
        for other in game_state.investigators.values():
            if self.instance_id in other.play_area:
                holder = other
                break
        if holder is None or holder.location_id != inv.location_id:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None:
            return False
        key = self._secrets(inst)
        if key is None or inst.uses.get(key, 0) < amount:
            return False
        inst.uses[key] -= amount
        inv.resources += amount
        game_state.log_effect(
            f"📖 肖夫纳商品目录：花费{amount}个秘密代付{amount}资源")

        # 秘密耗尽：弃置目录
        if inst.uses.get(key, 0) <= 0:
            vacate_asset_slots(game_state, self.instance_id)
            if self.instance_id in holder.play_area:
                holder.play_area.remove(self.instance_id)
            game_state.cards_in_play.pop(self.instance_id, None)
            holder.discard.append(self.card_id)
            game_state.log_effect("📖 肖夫纳商品目录：秘密耗尽，弃置")
        return True
