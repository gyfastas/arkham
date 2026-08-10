"""Shared base for "spend 1 resource: +1 <skill> this test" assets.

Used by: Physical Training, Arcane Studies, Hard Knocks, Dig Deep, Hyperawareness.

The boost is armed via `spend()` (called by session/UI when the player chooses
to pay). Spending N resources on a skill stacks to +N (official: the fast
ability may be used any number of times), and applies to the next
SKILL_VALUE_DETERMINED of the matching skill within the current test.
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ResourceSkillBoost(CardImplementation):
    """子类声明 boosted_skills: 该卡可花资源提升的技能列表。"""

    card_id = ""
    boosted_skills: tuple[Skill, ...] = ()

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        # 已武装的加值计数：{skill: 次数}（官方允许多次支付叠加）
        self._armed: dict[Skill, int] = {}

    def spend(self, game_state, investigator_id: str, skill: Skill) -> bool:
        """花费1资源：本次技能检定 +1 对应技能（可叠加）。"""
        if skill not in self.boosted_skills:
            return False
        inv = game_state.get_investigator(investigator_id)
        if inv is None or inv.resources < 1:
            return False
        if self.instance_id not in inv.play_area:
            return False
        inv.resources -= 1
        self._armed[skill] = self._armed.get(skill, 0) + 1
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_boost(self, ctx):
        count = self._armed.get(ctx.skill_type, 0)
        if not count:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        ctx.modify_amount(count, f"{self.card_id}_boost")
        self._armed.pop(ctx.skill_type, None)

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        # 未消耗的武装状态在检定结束后清除（资源已花不退）
        self._armed.clear()


# ----------------------------------------------------------------------
# 共享辅助：卡牌代码只持有 EventBus 句柄（register 时保存），无法访问
# DamageEngine 的私有方法；以下函数镜像引擎的击败/离场流程供卡牌效果使用。
# ----------------------------------------------------------------------


def deal_damage_to_enemy(game_state, bus, enemy_instance_id, amount,
                         defeated_by=None) -> bool:
    """对敌人造成伤害并处理击败。返回是否击败。

    与 DamageEngine.deal_damage_to_enemy 的差异：不走 DAMAGE_DEALT 修改窗口
    （引擎私有通道），与 guard_dog / dynamite_blast 的直接加减一致。
    """
    enemy = game_state.get_card_instance(enemy_instance_id)
    if enemy is None or amount <= 0:
        return False
    data = game_state.get_card_data(enemy.card_id)
    if data is None:
        return False
    enemy.damage += amount
    if data.enemy_health and enemy.damage >= data.enemy_health:
        defeat_enemy(game_state, bus, enemy_instance_id, defeated_by=defeated_by)
        return True
    return False


def defeat_enemy(game_state, bus, enemy_instance_id, defeated_by=None) -> None:
    """击败敌人：ENEMY_DEFEATED 事件 + 胜利牌堆 + 离场（镜像 DamageEngine）。"""
    from backend.engine.event_bus import EventContext

    enemy = game_state.get_card_instance(enemy_instance_id)
    if enemy is None:
        return
    if bus is not None:
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.ENEMY_DEFEATED,
            target=enemy_instance_id,
            investigator_id=defeated_by,
            extra={"card_id": enemy.card_id},
        ))
    data = game_state.get_card_data(enemy.card_id)
    if data is not None and getattr(data, "victory", 0):
        game_state.scenario.victory_display.append(enemy.card_id)
    game_state.cards_in_play.pop(enemy_instance_id, None)
    for inv in game_state.investigators.values():
        if enemy_instance_id in inv.threat_area:
            inv.threat_area.remove(enemy_instance_id)
    for loc in game_state.locations.values():
        if enemy_instance_id in loc.enemies:
            loc.enemies.remove(enemy_instance_id)
    game_state.scenario.encounter_discard.append(enemy.card_id)


def defeat_asset(game_state, bus, instance_id) -> None:
    """支援卡被击败/弃置离场（镜像 DamageEngine 的移除流程）。"""
    from backend.engine.event_bus import EventContext

    card = game_state.get_card_instance(instance_id)
    if card is None:
        return
    if bus is not None:
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.ASSET_DEFEATED,
            target=instance_id,
        ))
    game_state.cards_in_play.pop(instance_id, None)
    inv = game_state.get_investigator(card.owner_id)
    if inv is not None and instance_id in inv.play_area:
        inv.play_area.remove(instance_id)
        inv.discard.append(card.card_id)
    slot_mgr = getattr(game_state, "slot_managers", {}).get(card.owner_id)
    if slot_mgr is not None:
        slot_mgr.vacate(instance_id)
    if bus is not None:
        bus.emit(EventContext(
            game_state=game_state,
            event=GameEvent.CARD_LEAVES_PLAY,
            investigator_id=card.owner_id,
            target=instance_id,
            extra={"card_id": card.card_id},
        ))


def find_holder(game_state, card_id):
    """返回手牌中含 card_id 的第一位调查员（手牌自动打出类效果的持有者）。"""
    for inv in game_state.investigators.values():
        if card_id in inv.hand:
            return inv
    return None
