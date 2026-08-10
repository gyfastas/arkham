"""Lantern (Level 0) — Survivor Asset, Hand slot.
[action]：调查。本次调查中你所在地点-1隐藏值。
[action] 丢弃提灯：对你所在地点的一个敌人造成1点伤害。本行动不会引起
趁乱攻击。

简化说明：
- 调查能力沿用 Flashlight 的"启动武装"模式：activate() 武装后由会话层
  发起调查；仅对调查行动（INVESTIGATE_ACTION_INITIATED 跟踪）的智力检定
  降低难度（隐藏值-1），普通智力检定不受影响。
- 打伤害能力：activate_deal_damage() 丢弃提灯并对目标造成1伤害（默认选
  所在地点第一个敌人，可传 enemy_instance_id 指定）；击败结算为内联复制
  （卡牌代码访问不到 DamageEngine，同 aquinnah 模式）。
- "不会引起趁乱攻击"需会话层 AoO 钩子支持（引擎/会话缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class Lantern(CardImplementation):
    card_id = "lantern_lv0"
    activations = [
        {
            "id": "investigate",
            "label": "调查：本次调查所在地点-1隐藏值",
            "method": "activate",
            "actions": 1,
        },
        {
            "id": "deal_damage",
            "label": "丢弃提灯：对所在地点一个敌人造成1点伤害",
            "method": "activate_deal_damage",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._armed = False            # 调查-1隐藏值已武装
        self._investigating: str | None = None

    def activate(self, game_state, investigator_id: str) -> bool:
        """[action] 调查：本次调查所在地点-1隐藏值（武装后由会话层发起调查）。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        self._armed = True
        return True

    def activate_deal_damage(
        self, game_state, investigator_id: str, enemy_instance_id: str | None = None
    ) -> bool:
        """[action] 丢弃提灯：对你所在地点的一个敌人造成1点伤害。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False

        enemy_iid = enemy_instance_id or self._first_enemy_at_location(
            game_state, inv.location_id)
        enemy = game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            return False

        # 丢弃提灯
        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)

        # 造成1点伤害（击败结算内联复制引擎流程）
        enemy.damage += 1
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is not None and enemy_data.enemy_health \
                and enemy.damage >= enemy_data.enemy_health:
            if getattr(enemy_data, "victory", 0):
                game_state.scenario.victory_display.append(enemy.card_id)
            game_state.cards_in_play.pop(enemy_iid, None)
            for other in game_state.investigators.values():
                if enemy_iid in other.threat_area:
                    other.threat_area.remove(enemy_iid)
            for loc in game_state.locations.values():
                if enemy_iid in loc.enemies:
                    loc.enemies.remove(enemy_iid)
            game_state.scenario.encounter_discard.append(enemy.card_id)
            game_state.log_effect(
                f"🏮 提灯：【{game_state.card_name(enemy.card_id)}】被击败")
        else:
            game_state.log_effect(
                f"🏮 提灯：丢弃，对【{game_state.card_name(enemy.card_id)}】造成1点伤害")
        return True

    @staticmethod
    def _first_enemy_at_location(game_state, location_id) -> str | None:
        """所在地点的第一个敌人：未交战的优先，其次与当地点调查员交战的。"""
        loc = game_state.get_location(location_id)
        if loc is not None and loc.enemies:
            return loc.enemies[0]
        for other in game_state.investigators.values():
            if other.location_id == location_id and other.threat_area:
                return other.threat_area[0]
        return None

    @on_event(GameEvent.INVESTIGATE_ACTION_INITIATED, priority=TimingPriority.AFTER)
    def track_investigate(self, ctx):
        self._investigating = ctx.investigator_id

    @on_event(GameEvent.SKILL_TEST_BEGINS, priority=TimingPriority.WHEN)
    def lower_shroud(self, ctx):
        """调查检定时：隐藏值（难度）-1。"""
        if not self._armed or ctx.skill_type != Skill.INTELLECT:
            return
        if self._investigating != ctx.investigator_id:
            return
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        if ctx.difficulty is not None and ctx.difficulty > 0:
            ctx.difficulty = max(0, ctx.difficulty - 1)
            ctx.extra["lantern_lowered"] = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed = False
        self._investigating = None
