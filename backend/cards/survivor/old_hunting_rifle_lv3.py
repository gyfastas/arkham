"""Old Hunting Rifle (Level 3) — Survivor Asset, Hand x2 slot. (04273)
Uses (3 ammo).
[action] Spend 1 ammo: Fight. You get +3 [combat] and deal +2 damage for
this attack. If a [skull] or [auto_fail] symbol is revealed during this
attack, the rifle jams. (This attack automatically fails. Before you can
activate this ability again, you must perform the following ability:
"[action]: You clear the jam.")

简化说明：
- 弹药在发起攻击时（FIGHT_ACTION_INITIATED）扣除；卡壳或无弹药时取消
  攻击（引擎支持 FIGHT_ACTION_INITIATED cancel，行动不消耗）。
- 揭示骷髅/自动失败标记即卡壳：骷髅标记经 ctx.extra["force_auto_fail"]
  使本次攻击自动失败；自动失败标记本身即失败。
- 排除卡壳为启动能力（activations 声明，1行动）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import (
    ChaosTokenType, GameEvent, Skill, TimingPriority,
)

_JAM_TOKENS = {ChaosTokenType.SKULL, ChaosTokenType.AUTO_FAIL}


class OldHuntingRifle(CardImplementation):
    card_id = "old_hunting_rifle_lv3"
    activations = [{
        "id": "clear_jam",
        "label": "排除卡壳",
        "method": "clear_jam",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._jammed = False
        self._attack_armed = False  # 本次攻击已支付弹药

    def clear_jam(self, game_state, investigator_id: str) -> bool:
        """[action] 排除卡壳。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        if not self._jammed:
            return False
        self._jammed = False
        game_state.log_effect("🦌 老猎枪：排除卡壳")
        return True

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def spend_ammo(self, ctx):
        """[action] 花费1弹药：攻击。卡壳/无弹药时无法启动（取消攻击）。"""
        if ctx.source != self.instance_id:
            return
        if self._jammed:
            ctx.cancel()
            ctx.game_state.log_effect("🦌 老猎枪：已卡壳，需先排除卡壳")
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None:
            return
        if card.uses.get("ammo", 0) < 1:
            ctx.cancel()
            ctx.game_state.log_effect("🦌 老猎枪：没有弹药，无法攻击")
            return
        card.uses["ammo"] -= 1
        self._attack_armed = True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击 +3 战斗。"""
        if ctx.source != self.instance_id or not self._attack_armed:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(3, "old_hunting_rifle_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """本次攻击 +2 伤害（经 bonus_damage 通道汇入战斗结算）。"""
        if ctx.source != self.instance_id or not self._attack_armed:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        ctx.extra["bonus_damage"] = ctx.extra.get("bonus_damage", 0) + 2

    @on_event(GameEvent.CHAOS_TOKEN_RESOLVED, priority=TimingPriority.WHEN)
    def jam_on_bad_token(self, ctx):
        """揭示骷髅/自动失败：卡壳；骷髅标记时本次攻击自动失败。"""
        if ctx.source != self.instance_id or not self._attack_armed:
            return
        if ctx.chaos_token not in _JAM_TOKENS:
            return
        self._jammed = True
        if ctx.chaos_token == ChaosTokenType.SKULL:
            ctx.extra["force_auto_fail"] = True
        ctx.game_state.log_effect("🦌 老猎枪：卡壳！本次攻击自动失败")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        if ctx.source == self.instance_id:
            self._attack_armed = False
