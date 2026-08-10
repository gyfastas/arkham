"""Mk 1 Grenades (Level 4) — Guardian Asset. (05273)
使用(3补给)。如果Mk 1手雷没有补给，弃置它。
[行动]花费1补给：攻击。本次攻击你获得+2战斗。如果本次攻击成功，
不造成标准伤害，改为对被攻击敌人所在地点的每个敌人和每位其他调查员
造成2点伤害（任何额外伤害对被攻击的敌人造成）。

简化说明：
- 补给在 FIGHT_ACTION_INITIATED（以本卡发起攻击）时扣除（同 rolands 约定）；
  0补给时攻击被取消（本能力以补给为费用）。
- "被攻击敌人所在地点"：交战敌人取交战调查员所在地点，否则取敌人所在地点。
- 范围伤害：被攻击的敌人得 2+额外伤害（经 bonus_damage 通道汇入引擎标准
  结算）；同地点其他敌人各2点（经 _shared.deal_damage_to_enemy，含击败流程）；
  同地点每位其他调查员各2点（直接增减，同 dynamite_blast，注明未经分配窗口）。
- 补给耗尽时自动弃置本卡。
- 数据修正：卡牌数据 uses 键为 "suppliess"（源数据笔误），读取时两键兼容。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority

_SUPPLIES_KEYS = ("supplies", "suppliess")  # 数据键笔误兼容
_AOE_DAMAGE = 2


def _get_supplies(inst) -> int:
    for key in _SUPPLIES_KEYS:
        if key in inst.uses:
            return inst.uses[key]
    return 0


class Mk1Grenades(CardImplementation):
    card_id = "mk_1_grenades_lv4"

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._bus = None
        self._paid = False
        self._target: str | None = None

    def register(self, bus, instance_id: str) -> None:
        super().register(bus, instance_id)
        self._bus = bus

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def pay_supply(self, ctx):
        """扣1补给作为攻击费用；没有补给则无法攻击。"""
        self._paid = False
        self._target = None
        if ctx.source != self.instance_id:
            return
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is None or _get_supplies(card) <= 0:
            ctx.cancel()
            ctx.game_state.log_effect("💣 Mk 1手雷：没有补给，无法攻击")
            return
        for key in _SUPPLIES_KEYS:
            if key in card.uses and card.uses[key] > 0:
                card.uses[key] -= 1
                break
        self._paid = True
        self._target = ctx.enemy_id

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        """本次攻击 +2 战斗。"""
        if ctx.source != self.instance_id or not self._paid:
            return
        if ctx.skill_type == Skill.COMBAT:
            ctx.modify_amount(2, "mk_1_grenades_combat_bonus")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.AFTER)
    def area_damage(self, ctx):
        """成功：同地点每个敌人/其他调查员2点；被攻击敌人 2+额外伤害。"""
        if ctx.source != self.instance_id or not self._paid:
            return
        if ctx.skill_type != Skill.COMBAT:
            return
        bonus = int(ctx.extra.get("bonus_damage", 0) or 0)
        # 被攻击敌人：标准伤害1替换为2，额外伤害照加
        ctx.extra["bonus_damage"] = bonus + (_AOE_DAMAGE - 1)

        target_iid = self._target
        location_id = self._enemy_location(ctx, target_iid)
        if location_id is None:
            return

        # 同地点其他敌人各2点
        enemy_iids = set()
        loc = ctx.game_state.get_location(location_id)
        if loc is not None:
            enemy_iids.update(loc.enemies)
        for other in ctx.game_state.get_investigators_at_location(location_id):
            enemy_iids.update(other.threat_area)
        for enemy_iid in sorted(enemy_iids):
            if enemy_iid == target_iid:
                continue
            deal_damage_to_enemy(
                ctx.game_state, self._bus, enemy_iid, _AOE_DAMAGE,
                defeated_by=ctx.investigator_id,
            )

        # 同地点每位其他调查员各2点（直接结算，同 dynamite_blast）
        for other in ctx.game_state.get_investigators_at_location(location_id):
            if other.investigator_id == ctx.investigator_id:
                continue
            other.damage += _AOE_DAMAGE
        ctx.extra["mk_1_grenades_aoe"] = location_id
        ctx.game_state.log_effect(
            f"💣 Mk 1手雷：同地点敌人与其他调查员各受{_AOE_DAMAGE}点伤害")

        # 补给耗尽：弃置本卡
        card = ctx.game_state.get_card_instance(self.instance_id)
        if card is not None and _get_supplies(card) <= 0:
            inv = ctx.game_state.get_investigator(card.owner_id)
            if inv is not None:
                vacate_asset_slots(ctx.game_state, self.instance_id)
                if self.instance_id in inv.play_area:
                    inv.play_area.remove(self.instance_id)
                ctx.game_state.cards_in_play.pop(self.instance_id, None)
                inv.discard.append(self.card_id)
                ctx.game_state.log_effect("💣 Mk 1手雷：补给耗尽，弃置")

    @staticmethod
    def _enemy_location(ctx, enemy_iid) -> str | None:
        """敌人所在地点：交战敌人取交战调查员地点，否则取地点列表。"""
        if enemy_iid is None:
            return None
        for inv in ctx.game_state.investigators.values():
            if enemy_iid in inv.threat_area:
                return inv.location_id
        for loc in ctx.game_state.locations.values():
            if enemy_iid in loc.enemies:
                return loc.location_id
        return None

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._paid = False
        self._target = None
