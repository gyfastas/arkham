"""Custom Ammunition (Level 3) — Guardian Event. (04193)
快速。仅在你的回合中打出。
叠加到你所在地点一名调查员控制的一张[[Firearm]]支援卡上。在该支援卡上
放置2弹药。每张卡限制1张。
被叠加卡进行的攻击对[[Monster]]敌人造成+1伤害。

简化说明：
- 叠加目标自动选择：优先你自己装备区第一张 firearm 卡，其次同地点其他
  调查员的（会话层 PLAY 通道不传目标；可经 ctx.extra["custom_ammo_target"]
  指定实例）。已有特制弹药叠加的卡跳过（每张限1）。
- 叠加关系记录在 scenario.vars["custom_ammunition"]（{weapon_iid: owner}），
  事件卡结算后入弃牌堆（引擎事件卡生命周期，叠加的实体表示未实现，
  同 snare_trap/ambush 惯例）。
- +1伤害经 DAMAGE_DEALT 修改窗口（目标敌人带 monster 特质时）。
- ⚠️ 事件实现实例在 ROUND_ENDS 被引擎清理，跨回合后 +1 伤害不再生效
  （引擎缺口，同 snare_trap/barricade 跨轮监听缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority

VAR = "custom_ammunition"


class CustomAmmunition(CardImplementation):
    card_id = "custom_ammunition_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach_and_reload(self, ctx):
        """打出时：叠加到同地点一张 firearm 卡上并放置2弹药。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        attached = ctx.game_state.scenario.vars.setdefault(VAR, {})

        target_iid = ctx.extra.get("custom_ammo_target")
        if target_iid is None or target_iid in attached:
            target_iid = self._pick_firearm(ctx.game_state, inv, attached)
        if target_iid is None:
            ctx.extra["custom_ammo_fizzle"] = True
            ctx.game_state.log_effect("🔧 特制弹药：没有可叠加的枪械，效果不结算")
            return
        weapon = ctx.game_state.get_card_instance(target_iid)
        weapon.uses["ammo"] = weapon.uses.get("ammo", 0) + 2
        attached[target_iid] = inv.investigator_id
        ctx.extra["custom_ammo_attached"] = target_iid
        ctx.game_state.log_effect(
            f"🔧 特制弹药：叠加到【{ctx.game_state.card_name(weapon.card_id)}】，"
            "放置2弹药")

    @staticmethod
    def _pick_firearm(game_state, inv, attached) -> str | None:
        """自动选择：优先自己装备区的 firearm，其次同地点其他调查员的。"""
        candidates = [inv] + [
            other for other in game_state.get_investigators_at_location(inv.location_id)
            if other.investigator_id != inv.investigator_id
        ]
        for candidate in candidates:
            for iid in candidate.play_area:
                if iid in attached:
                    continue
                inst = game_state.get_card_instance(iid)
                data = game_state.get_card_data(inst.card_id) if inst else None
                if data is not None and "firearm" in (data.traits or []):
                    return iid
        return None

    @on_event(GameEvent.DAMAGE_DEALT, priority=TimingPriority.WHEN)
    def bonus_vs_monster(self, ctx):
        """被叠加卡的攻击对 Monster 敌人 +1 伤害。"""
        attached = ctx.game_state.scenario.vars.get(VAR, {})
        if ctx.source not in attached:
            return
        enemy = ctx.game_state.get_card_instance(ctx.target) if ctx.target else None
        enemy_data = ctx.game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy_data is None or "monster" not in (enemy_data.traits or []):
            return
        ctx.modify_amount(1, "custom_ammunition_bonus")
        ctx.game_state.log_effect("🔧 特制弹药：对怪物敌人+1伤害")
