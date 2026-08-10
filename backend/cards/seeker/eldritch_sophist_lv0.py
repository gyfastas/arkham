"""Eldritch Sophist (Level 0) — Seeker Asset, Ally slot. (07111)
使用(3秘密)。
[快速]横置诡秘辩士：将你控制的一张资产上的1个秘密或充能移动到你所在地点
一名调查员控制的另一张资产上。

简化说明：
- 来源/目标资产缺省自动选择：来源优先本卡（有秘密时），否则你控制的第一张
  带秘密或充能的资产；目标为同地点调查员控制的第一张"另一张"资产
  （activate(source_instance_id=..., target_instance_id=..., token_type=...)
  可显式指定，官方为玩家自选）；
- 移动的标记类型缺省取秘密（来源无秘密时取充能）；目标无对应 uses 键时
  新建计数；
- 数据 uses 键兼容双 s 写法（"secretss"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation
from backend.cards.seeker._uses import uses_count, uses_key, uses_spend

_TOKEN_TYPES = ("secrets", "charges")


class EldritchSophist(CardImplementation):
    card_id = "eldritch_sophist_lv0"
    activations = [{
        "id": "move_token",
        "label": "[快速]横置：移动1个秘密/充能到另一张资产",
        "method": "activate",
    }]

    def activate(self, game_state, investigator_id: str,
                 source_instance_id: str | None = None,
                 target_instance_id: str | None = None,
                 token_type: str | None = None) -> bool:
        """[快速]横置：把来源资产的1个秘密/充能移动到目标资产。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted:
            return False

        source = self._resolve_source(game_state, inv, source_instance_id)
        if source is None:
            return False
        if token_type is None:
            token_type = next(
                (t for t in _TOKEN_TYPES if uses_count(source, t) > 0), None)
        if token_type is None or uses_count(source, token_type) <= 0:
            return False
        target = self._resolve_target(game_state, inv, source.instance_id,
                                      target_instance_id)
        if target is None:
            return False

        inst.exhausted = True
        uses_spend(source, token_type)
        key = uses_key(target, token_type)
        target.uses[key] = target.uses.get(key, 0) + 1
        game_state.log_effect(
            f"🎓 诡秘辩士：横置，【{game_state.card_name(source.card_id)}】的"
            f"1个{token_type}移到【{game_state.card_name(target.card_id)}】"
        )
        return True

    def _resolve_source(self, game_state, inv, instance_id):
        """来源：你控制的带秘密/充能的资产（缺省本卡优先）。"""
        if instance_id is not None:
            if instance_id not in inv.play_area:
                return None
            ci = game_state.get_card_instance(instance_id)
            has = ci is not None and any(
                uses_count(ci, t) > 0 for t in _TOKEN_TYPES)
            return ci if has else None
        own = game_state.get_card_instance(self.instance_id)
        if own is not None and uses_count(own, "secrets") > 0:
            return own
        for iid in inv.play_area:
            ci = game_state.get_card_instance(iid)
            if ci is not None and any(
                    uses_count(ci, t) > 0 for t in _TOKEN_TYPES):
                return ci
        return None

    def _resolve_target(self, game_state, inv, source_id, instance_id):
        """目标：你所在地点任一调查员控制的"另一张"资产（缺省第一张）。"""
        investigators = game_state.get_investigators_at_location(inv.location_id)
        if instance_id is not None:
            if instance_id == source_id:
                return None
            for other in investigators:
                if instance_id in other.play_area:
                    return game_state.get_card_instance(instance_id)
            return None
        for other in investigators:
            for iid in other.play_area:
                if iid == source_id:
                    continue
                ci = game_state.get_card_instance(iid)
                if ci is not None:
                    return ci
        return None
