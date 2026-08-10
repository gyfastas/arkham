"""Augur (Level 0) — Survivor Asset, Ally. Bonded (Miss Doyle). Fast.
强制 - 预见入场后：丢弃希望(hope_lv0)和热诚(zeal_lv0)。
[行动] 若预见已准备，消耗或丢弃她：调查。以5点基础[智力]值调查。
（若丢弃了预见，本次检定自动成功。然后你可以将预见洗入牌库，
将希望或热诚从弃牌堆放置入场。）

简化说明：
- 调查行动由会话层发起；activate() 消耗（或经 discard=True 丢弃）预见并
  武装一次调查：下一次由控制者执行的智力检定以5为基础值（经
  SKILL_VALUE_DETERMINED 修正），丢弃武装时失败自动翻为成功。
- 丢弃后的收尾（自动执行，官方为"可以"选择）：预见放回牌库底
  （"洗入牌库"简化为置底，不随机洗牌，便于确定性测试），并将弃牌堆中
  第一张希望/热诚（优先希望）以新实例放置入场。
- "强制-丢弃希望和热诚"：入场时丢弃控制者游戏区中的 hope_lv0/zeal_lv0。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.models.state import CardInstance

_BONDED_IDS = ("hope_lv0", "zeal_lv0")


class Augur(CardImplementation):
    card_id = "augur_lv0"
    activations = [{
        "id": "investigate",
        "label": "[行动] 消耗或丢弃预见：以基础5智力调查",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # {"auto": bool} 武装一次以5为基础智力的调查
        self._armed: dict | None = None
        self._owner_id: str | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def discard_bonded(self, ctx):
        """强制 - 入场后：丢弃希望和热诚。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inst = ctx.game_state.get_card_instance(ctx.target or "")
        owner_id = inst.owner_id if inst is not None else ctx.investigator_id
        owner = ctx.game_state.get_investigator(owner_id)
        if owner is None:
            return
        for iid in list(owner.play_area):
            other = ctx.game_state.get_card_instance(iid)
            if other is None or other.card_id not in _BONDED_IDS:
                continue
            vacate_asset_slots(ctx.game_state, iid)
            owner.play_area.remove(iid)
            ctx.game_state.cards_in_play.pop(iid, None)
            owner.discard.append(other.card_id)
            ctx.game_state.log_effect(
                f"🐈 预见：强制丢弃【{ctx.game_state.card_name(other.card_id)}】")

    def activate(self, game_state, investigator_id: str, discard: bool = False) -> bool:
        """[行动] 消耗（或丢弃）预见：武装一次以5为基础智力的调查。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return False
        if self.instance_id not in inv.play_area:
            return False
        if discard:
            vacate_asset_slots(game_state, self.instance_id)
            inv.play_area.remove(self.instance_id)
            game_state.cards_in_play.pop(self.instance_id, None)
            inv.discard.append(self.card_id)
        else:
            inst.exhausted = True
        self._armed = {"auto": discard}
        self._owner_id = investigator_id
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def base_intellect_five(self, ctx):
        if self._armed is None or ctx.investigator_id != self._owner_id:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        base = ctx.extra.get("base_skill")
        if base is None:
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            base = inv.get_skill(Skill.INTELLECT) if inv else 0
        ctx.modify_amount(5 - base, "augur_base_intellect")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.WHEN)
    def auto_success(self, ctx):
        """丢弃预见的调查自动成功。"""
        if self._armed is None or not self._armed.get("auto"):
            return
        if ctx.investigator_id != self._owner_id:
            return
        if ctx.skill_type != Skill.INTELLECT:
            return
        ctx.success = True
        ctx.extra["augur_auto_success"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def cleanup_and_revive(self, ctx):
        """丢弃武装的调查结束后：预见洗入牌库，希望/热诚从弃牌堆入场。"""
        try:
            if self._armed is None or ctx.investigator_id != self._owner_id:
                return
            if not self._armed.get("auto"):
                return
            inv = ctx.game_state.get_investigator(ctx.investigator_id)
            if inv is None:
                return
            # 预见洗入牌库（简化：置底不洗牌）
            if self.card_id in inv.discard:
                inv.discard.remove(self.card_id)
                inv.deck.append(self.card_id)
            # 弃牌堆中第一张希望/热诚放置入场（优先希望）
            for bonded_id in _BONDED_IDS:
                if bonded_id not in inv.discard:
                    continue
                inv.discard.remove(bonded_id)
                new_iid = ctx.game_state.next_instance_id()
                cd = ctx.game_state.get_card_data(bonded_id)
                ctx.game_state.cards_in_play[new_iid] = CardInstance(
                    instance_id=new_iid,
                    card_id=bonded_id,
                    owner_id=inv.investigator_id,
                    controller_id=inv.investigator_id,
                    slot_used=list(getattr(cd, "slots", None) or []),
                )
                inv.play_area.append(new_iid)
                ctx.extra["augur_revived"] = bonded_id
                ctx.game_state.log_effect(
                    f"🐈 预见：洗入牌库，【{ctx.game_state.card_name(bonded_id)}】入场")
                break
        finally:
            self._armed = None
            self._owner_id = None
