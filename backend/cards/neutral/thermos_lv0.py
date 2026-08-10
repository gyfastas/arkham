"""Thermos (Level 0) — Neutral Asset.
使用（3补给）。
[行动]花费1补给，横置保温瓶：治愈你所在地点一名调查员的1点伤害
（若其有2个或以上肉体创伤，改为治愈2点伤害）。
[行动]花费1补给，横置保温瓶：治愈你所在地点一名调查员的1点恐惧
（若其有2个或以上精神创伤，改为治愈2点恐惧）。

简化说明：
- 数据文件中 uses 键存在笔误（"suppliess"），入场时规范化为 "supplies"。
- 创伤计数同时读取 investigator_card.physical_trauma/mental_trauma（战役
  状态）与 InvestigatorState 上的同名动态属性（部分弱点直接写 state）。
- 通用激活通道只传 (game_state, investigator_id)，默认治愈自己；会话层
  可传 target_investigator_id 指定同地点的其他调查员（同 first_aid_lv0）。
- 卡面无"补给耗尽即弃置"语句：补给用完后保温瓶留在场上。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority


class Thermos(CardImplementation):
    card_id = "thermos_lv0"
    activations = [
        {"id": "heal_damage", "label": "[行动]花1补给横置：治愈伤害（2+肉体创伤时治2）",
         "method": "activate_heal_damage", "actions": 1},
        {"id": "heal_horror", "label": "[行动]花1补给横置：治愈恐惧（2+精神创伤时治2）",
         "method": "activate_heal_horror", "actions": 1},
    ]

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def normalize_uses_key(self, ctx):
        """数据笔误 "suppliess" → "supplies"（入场时一次性规范化）。"""
        if ctx.target != self.instance_id:
            return
        inst = ctx.game_state.get_card_instance(self.instance_id)
        if inst is None:
            return
        if "suppliess" in inst.uses and "supplies" not in inst.uses:
            inst.uses["supplies"] = inst.uses.pop("suppliess")

    def activate_heal_damage(self, game_state, investigator_id: str,
                             target_investigator_id: str | None = None) -> bool:
        return self._heal(game_state, investigator_id,
                          target_investigator_id, kind="damage")

    def activate_heal_horror(self, game_state, investigator_id: str,
                             target_investigator_id: str | None = None) -> bool:
        return self._heal(game_state, investigator_id,
                          target_investigator_id, kind="horror")

    def _heal(self, game_state, investigator_id, target_investigator_id,
              kind: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area or inst.exhausted:
            return False
        if inst.uses.get("supplies", 0) <= 0:
            return False

        target = game_state.get_investigator(target_investigator_id or investigator_id)
        if target is None or target.location_id != inv.location_id:
            return False

        if kind == "damage":
            if target.damage <= 0:
                return False
            amount = 2 if self._trauma(target, "physical") >= 2 else 1
            target.damage = max(0, target.damage - amount)
        else:
            if target.horror <= 0:
                return False
            amount = 2 if self._trauma(target, "mental") >= 2 else 1
            target.horror = max(0, target.horror - amount)

        inst.uses["supplies"] -= 1
        inst.exhausted = True
        game_state.log_effect(
            f"☕ 保温瓶：治愈【{target.investigator_id}】{amount}点"
            f"{'伤害' if kind == 'damage' else '恐惧'}"
        )
        return True

    @staticmethod
    def _trauma(inv, kind: str) -> int:
        """创伤计数：战役状态（investigator_card）+ state 动态属性。"""
        ic = inv.investigator_card
        from_card = getattr(ic, f"{kind}_trauma", 0) if ic is not None else 0
        from_state = getattr(inv, f"{kind}_trauma", 0)
        return (from_card or 0) + (from_state or 0)
