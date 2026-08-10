"""Spirit-Speaker (Level 0) — Neutral Asset, Signature (Akachi Onyele).
[fast]消耗灵言者：选择你控制的一张带有"使用(充能)"的支援卡。该支援卡返回
你的手牌，或者将该支援卡上所有的充能（作为资源）移动到你的资源池并丢弃该支援卡。

简化说明：
- 未指定目标时自动选择你控制的第一张带充能的支援卡（官方为玩家选择）；
  会话层可传 target_instance_id 与 mode（"return"/"cash"）覆盖。
"""

from backend.cards.base import CardImplementation
from backend.models.enums import CardType


class SpiritSpeaker(CardImplementation):
    card_id = "spirit_speaker_lv0"
    activations = [{"id": "resolve", "label": "[fast]消耗灵言者：回收或兑现充能", "method": "activate_resolve"}]

    def list_targets(self, game_state, investigator_id) -> list[str]:
        """你控制的带"使用(充能)"的支援卡 instance_id 列表。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return []
        out = []
        for iid in inv.play_area:
            inst = game_state.get_card_instance(iid)
            if inst is None or iid == self.instance_id:
                continue
            cd = game_state.get_card_data(inst.card_id)
            if cd is not None and cd.type == CardType.ASSET and "charges" in inst.uses:
                out.append(iid)
        return out

    def activate_resolve(self, game_state, investigator_id,
                         target_instance_id: str | None = None,
                         mode: str = "return") -> bool:
        """[fast]消耗灵言者：回收目标到手牌，或兑现其全部充能并丢弃。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        speaker = game_state.get_card_instance(self.instance_id)
        if speaker is None or self.instance_id not in inv.play_area:
            return False
        if speaker.exhausted:
            return False

        targets = self.list_targets(game_state, investigator_id)
        if target_instance_id is not None:
            if target_instance_id not in targets:
                return False
            chosen = target_instance_id
        elif targets:
            chosen = targets[0]  # 简化：自动选择第一张
        else:
            return False

        speaker.exhausted = True
        inst = game_state.get_card_instance(chosen)
        inv.play_area.remove(chosen)
        game_state.cards_in_play.pop(chosen, None)

        if mode == "cash":
            charges = inst.uses.get("charges", 0)
            inv.resources += charges
            inv.discard.append(inst.card_id)
            game_state.log_effect(
                f"🔮 灵言者：【{game_state.card_name(inst.card_id)}】的"
                f"{charges}个充能转化为资源"
            )
        else:
            inv.hand.append(inst.card_id)
            game_state.log_effect(
                f"🔮 灵言者：【{game_state.card_name(inst.card_id)}】返回手牌"
            )
        return True
