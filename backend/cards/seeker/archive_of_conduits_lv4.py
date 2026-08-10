"""Archive of Conduits (Level 4) — Seeker Asset, Arcane slot. (08044)
已研究。使用(4地线)。每牌组限1张。
[快速]：将本支援上的1条地线移动到一名调查员上。
[行动]：选择一名带有地线的调查员。该调查员抽1张牌并治疗1点伤害或1点恐惧。
你可以移除其上的地线，改为抽2张牌并治疗2点伤害或2点恐惧。

简化说明：
- 地线台账与 archive_of_conduits_lv0 共用 scenario.vars["leylines"]；
- 目标调查员缺省为你自己（activate(target_investigator_id=...) 可指定同
  地点其他调查员；[快速]移动官方可选任意调查员，此处同样默认自己）；
- "治疗1点伤害或1点恐惧"自动选择：优先伤害，其次恐惧（heal_kind= 可指定）；
- "你可以移除地线改为抽2治2"由 remove_leyline=True 触发，缺省不移除
  （保守，不消耗资源）；
- 数据 uses 键兼容双 s 写法（"leyliness"），见 seeker/_uses.py。
"""

from backend.cards.base import CardImplementation, on_event
from backend.cards.seeker._uses import uses_key, uses_spend
from backend.models.enums import GameEvent, TimingPriority

from backend.cards.seeker.archive_of_conduits_lv0 import leyline_store


class ArchiveOfConduitsLv4(CardImplementation):
    card_id = "archive_of_conduits_lv4"
    activations = [
        {"id": "move_leyline", "label": "[快速]将1条地线移动到一名调查员上",
         "method": "activate_move"},
        {"id": "channel", "label": "[行动]选择带地线的调查员：抽1并治疗1",
         "method": "activate", "actions": 1},
    ]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def normalize_uses(self, ctx):
        """入场：规范化数据 uses 键（"leyliness"→"leylines"）。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        key = uses_key(inst, "leylines")
        if key != "leylines":
            inst.uses["leylines"] = inst.uses.pop(key)
        inst.uses.setdefault("leylines", 4)

    def activate_move(self, game_state, investigator_id: str,
                      target_investigator_id: str | None = None) -> bool:
        """[快速]：将本支援上的1条地线移动到一名调查员上（默认自己）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or not uses_spend(inst, "leylines"):
            return False
        target = game_state.get_investigator(target_investigator_id
                                             or investigator_id)
        if target is None:
            return False
        store = leyline_store(game_state)
        invs = store["investigators"]
        invs[target.investigator_id] = invs.get(target.investigator_id, 0) + 1
        game_state.log_effect(
            f"🌀 导管档案(4)：1条地线移动到【{target.investigator_id}】上"
        )
        return True

    def activate(self, game_state, investigator_id: str,
                 target_investigator_id: str | None = None,
                 remove_leyline: bool = False,
                 heal_kind: str | None = None) -> bool:
        """[行动]：选择带地线的调查员（默认自己）：抽1并治疗1；
        remove_leyline=True 时移除地线，改为抽2并治疗2。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        target = game_state.get_investigator(target_investigator_id
                                             or investigator_id)
        if target is None:
            return False
        store = leyline_store(game_state)
        invs = store["investigators"]
        if invs.get(target.investigator_id, 0) <= 0:
            return False

        amount = 1
        if remove_leyline:
            invs[target.investigator_id] -= 1
            amount = 2

        for _ in range(amount):
            if target.deck:
                target.hand.append(target.deck.pop(0))
        healed = self._heal(target, amount, heal_kind)
        game_state.log_effect(
            f"🌀 导管档案(4)：【{target.investigator_id}】抽{amount}张牌，"
            f"治疗{healed}点{heal_kind or '伤害/恐惧'}"
        )
        return True

    @staticmethod
    def _heal(target, amount: int, heal_kind: str | None) -> int:
        """治疗 amount 点伤害/恐惧（缺省优先伤害）；返回实际治疗量。"""
        healed = 0
        for _ in range(amount):
            if heal_kind == "horror":
                pool = "horror"
            elif heal_kind == "damage":
                pool = "damage"
            else:
                pool = "damage" if target.damage > 0 else "horror"
            if pool == "damage" and target.damage > 0:
                target.damage -= 1
                healed += 1
            elif pool == "horror" and target.horror > 0:
                target.horror -= 1
                healed += 1
        return healed
