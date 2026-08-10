"""Enchant Weapon (Level 3) — Guardian Event. (07261)
叠加到你所在地点一名调查员控制的一张[[Weapon]]支援卡上。每张卡限制1张。
被叠加卡获得[[Relic]]特质，并在其原本槽位之外额外占用一个法术槽。
[反应]当你使用被叠加卡执行攻击行动时，横置本卡：将本卡拥有者的意志
加到你的战斗上，本次攻击造成+1伤害。

简化说明：
- 叠加目标自动选择：优先你自己装备区第一张 weapon 卡，其次同地点其他
  调查员的（可经 ctx.extra["enchant_weapon_target"] 指定实例）。已有附魔
  武器叠加的卡跳过（每张限1）。
- 叠加关系记录在 scenario.vars["enchant_weapon"]（{weapon_iid: {...}}），
  事件卡结算后入弃牌堆（引擎事件卡生命周期，叠加实体未实现，同 ambush
  惯例）。"获得Relic特质/额外法术槽"无引擎通道，未实现（引擎缺口）。
- 反应触发：FIGHT_ACTION_INITIATED（以被叠加卡发起攻击）时若未横置则
  自动横置（官方为玩家选择；纯收益自动发动），武装本次攻击：
  SKILL_VALUE_DETERMINED 加拥有者意志，成功时 +1 伤害。
- 横置状态在 UPKEEP_PHASE_BEGINS 恢复（镜像准备步骤）。
- ⚠️ 事件实现实例在 ROUND_ENDS 被引擎清理，跨回合后反应不再生效
  （引擎缺口，同 snare_trap/barricade 跨轮监听缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority

VAR = "enchant_weapon"


class EnchantWeapon(CardImplementation):
    card_id = "enchant_weapon_lv3"

    @on_event(GameEvent.CARD_PLAYED, priority=TimingPriority.WHEN)
    def attach(self, ctx):
        """打出时：叠加到同地点一张 weapon 卡上。"""
        if ctx.extra.get("card_id") != self.card_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        attached = ctx.game_state.scenario.vars.setdefault(VAR, {})

        target_iid = ctx.extra.get("enchant_weapon_target")
        if target_iid is None or target_iid in attached:
            target_iid = self._pick_weapon(ctx.game_state, inv, attached)
        if target_iid is None:
            ctx.extra["enchant_weapon_fizzle"] = True
            ctx.game_state.log_effect("✨ 附魔武器：没有可叠加的武器，效果不结算")
            return
        attached[target_iid] = {
            "owner_id": inv.investigator_id,
            "exhausted": False,
        }
        ctx.extra["enchant_weapon_attached"] = target_iid
        weapon = ctx.game_state.get_card_instance(target_iid)
        ctx.game_state.log_effect(
            f"✨ 附魔武器：叠加到【{ctx.game_state.card_name(weapon.card_id)}】")

    @staticmethod
    def _pick_weapon(game_state, inv, attached) -> str | None:
        """自动选择：优先自己装备区的 weapon，其次同地点其他调查员的。"""
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
                if data is not None and "weapon" in (data.traits or []):
                    return iid
        return None

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed_weapon = None  # 本次攻击的被叠加卡 instance_id

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def arm_on_fight(self, ctx):
        """以被叠加卡发起攻击时：自动横置附魔，武装本次攻击。"""
        self._armed_weapon = None
        attached = ctx.game_state.scenario.vars.get(VAR, {})
        record = attached.get(ctx.source)
        if record is None or record.get("exhausted"):
            return
        record["exhausted"] = True
        self._armed_weapon = ctx.source
        ctx.extra["enchant_weapon_empowered"] = ctx.source
        ctx.game_state.log_effect("✨ 附魔武器：横置，本次攻击加入意志并+1伤害")

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def add_willpower(self, ctx):
        """武装的攻击：将本卡拥有者的意志加到你的战斗上。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_weapon is None or ctx.source != self._armed_weapon:
            return
        record = ctx.game_state.scenario.vars.get(VAR, {}).get(ctx.source)
        owner = (
            ctx.game_state.get_investigator(record["owner_id"]) if record else None
        )
        if owner is None:
            return
        willpower = owner.get_skill(Skill.WILLPOWER)
        if willpower:
            ctx.modify_amount(willpower, "enchant_weapon_willpower")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def bonus_damage(self, ctx):
        """武装的攻击成功：+1伤害。"""
        if ctx.skill_type != Skill.COMBAT:
            return
        if self._armed_weapon is None or ctx.source != self._armed_weapon:
            return
        ctx.extra["bonus_damage"] = int(ctx.extra.get("bonus_damage", 0) or 0) + 1

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_weapon = None

    @on_event(GameEvent.UPKEEP_PHASE_BEGINS, priority=TimingPriority.AFTER)
    def ready_markers(self, ctx):
        """准备步骤：恢复所有被叠加卡的附魔横置状态。"""
        for record in ctx.game_state.scenario.vars.get(VAR, {}).values():
            record["exhausted"] = False
