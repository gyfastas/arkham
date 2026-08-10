"""Marksmanship (Level 1) — Guardian Event. (04104)
快速。在你启动一张[[枪械]]或[[远程]]支援卡上的攻击能力时打出。
本次攻击可以以连接地点的敌人为目标。本次攻击无视冷漠和报复关键词。
如果本次攻击对一个未与你交战的敌人成功，本次攻击造成+1伤害。

简化说明：
- 从手牌中自动触发（官方为玩家选择时机）：以你场上枪械/远程支援发起攻击时，
  若手牌中有本卡且资源足够，自动打出（同 eat_lead 的约定）。
- "连接地点目标"：引擎 _fight 不校验目标交战/地点（目标合法性由会话层
  负责），本卡无需额外处理（注明）。
- "无视冷漠"：引擎未实现 aloof 关键词（无法躲避的敌人需会话层过滤），
  无额外处理（注明）。
- "无视报复"：失败时引擎经 deal_damage 造成报复伤害（源为被攻击敌人），
  本卡在报复窗口内取消该次伤害/恐惧分配。
- +1伤害：目标不在你威胁区（未交战）时，成功经 bonus_damage 通道追加。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

_WEAPON_TRAITS = ("firearm", "ranged")


class Marksmanship(CardImplementation):
    card_id = "marksmanship_lv1"
    persistent_in_hand = True  # 手牌中持续监听攻击启动

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed: dict | None = None  # {"inv", "enemy"}
        self._retaliate_window: str | None = None  # 待取消报复伤害的敌人 id

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def auto_play(self, ctx):
        """以你的枪械/远程支援启动攻击时：自动打出。"""
        weapon_iid = ctx.source
        if weapon_iid is None:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.card_id not in inv.hand:
            return
        if weapon_iid not in inv.play_area:
            return
        weapon = ctx.game_state.get_card_instance(weapon_iid)
        weapon_data = ctx.game_state.get_card_data(weapon.card_id) if weapon else None
        if weapon_data is None:
            return
        if not any(t in (weapon_data.traits or []) for t in _WEAPON_TRAITS):
            return
        data = ctx.game_state.get_card_data(self.card_id)
        cost = (getattr(data, "cost", 2) or 2) if data else 2
        if inv.resources < cost:
            return

        inv.resources -= cost
        inv.hand.remove(self.card_id)
        inv.discard.append(self.card_id)
        self._armed = {"inv": inv.investigator_id, "enemy": ctx.enemy_id}
        ctx.extra["marksmanship_armed"] = True
        ctx.game_state.log_effect(
            "🎯 神射手：本次攻击无视冷漠/报复，可打连接地点目标")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """对未与你交战的敌人成功：+1伤害。"""
        armed = self._armed
        if armed is None or ctx.investigator_id != armed["inv"]:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        enemy_iid = armed["enemy"]
        if inv is not None and enemy_iid and enemy_iid not in inv.threat_area:
            ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1
            ctx.extra["marksmanship_bonus"] = True
            ctx.game_state.log_effect("🎯 神射手：目标未交战，+1伤害")

    @on_event(GameEvent.SKILL_TEST_FAILED, priority=TimingPriority.AFTER)
    def arm_retaliate_cancel(self, ctx):
        """攻击失败：标记报复窗口，取消其后的报复伤害/恐惧。"""
        armed = self._armed
        if armed is None or ctx.investigator_id != armed["inv"]:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        self._retaliate_window = armed["enemy"]

    @on_event(GameEvent.DAMAGE_ASSIGNED, priority=TimingPriority.WHEN)
    @on_event(GameEvent.HORROR_ASSIGNED, priority=TimingPriority.WHEN)
    def cancel_retaliate(self, ctx):
        """报复关键词造成的伤害/恐惧：取消。"""
        if self._retaliate_window is None:
            return
        if ctx.source != self._retaliate_window:
            return
        ctx.cancel()
        ctx.extra["marksmanship_retaliate_ignored"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = None
        self._retaliate_window = None
