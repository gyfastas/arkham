"""Fend Off (Level 3) — Survivor Event.
快速。在一名非[[精英]]敌人在你所在地点生成时打出。
该敌人攻击你。然后自动躲避该敌人并将抵挡叠加到它。
被叠加的敌人不能准备。

简化说明：
- 引擎没有通用的"敌人生成"事件（生成由剧本遭遇代码直接处理，
  见 official_core._spawn_enemy_from_encounter），打出窗口为引擎缺口：
  由会话层在生成时调用 resolve()（activations 已声明）。
- "该敌人攻击你"：卡牌代码访问不到 DamageEngine，伤害/恐惧为直接结算
  （不经过盟友分摊/取消窗口，简化记注）。
- "叠加到敌人"：抵挡本体进入弃牌堆，叠加关系记录在
  scenario.vars["fend_off_attached"]（引擎无跨卡叠加区）；
  "被叠加的敌人不能准备"经 CARD_READIED 处理（重新横置）——但事件牌的
  临时实现会在 ROUND_ENDS 被注销，跨轮持续生效需会话层保持注册
  （引擎缺口，见报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class FendOff(CardImplementation):
    card_id = "fend_off_lv3"
    activations = [{
        "id": "resolve",
        "label": "非精英敌人在你所在地点生成时打出：其攻击你后自动躲避之",
        "method": "resolve",
    }]

    def resolve(self, game_state, investigator_id: str,
                enemy_instance_id: str) -> bool:
        """敌人生成窗口：该敌人攻击你，然后自动躲避并叠加抵挡。"""
        inv = game_state.get_investigator(investigator_id)
        enemy = game_state.get_card_instance(enemy_instance_id)
        if inv is None or enemy is None:
            return False
        enemy_data = game_state.get_card_data(enemy.card_id)
        if enemy_data is None or is_elite_enemy(enemy_data):
            return False

        # 该敌人攻击你（简化：直接结算伤害/恐惧）
        inv.damage += enemy_data.enemy_damage or 0
        inv.horror += enemy_data.enemy_horror or 0

        # 自动躲避：横置并脱离交战，留在所在地点
        enemy.exhausted = True
        if enemy_instance_id in inv.threat_area:
            inv.threat_area.remove(enemy_instance_id)
        loc = game_state.get_location(inv.location_id)
        if loc is not None and enemy_instance_id not in loc.enemies:
            loc.enemies.append(enemy_instance_id)

        # 叠加抵挡：被叠加的敌人不能准备
        game_state.scenario.vars.setdefault(
            "fend_off_attached", {})[enemy_instance_id] = self.card_id
        if self.card_id not in inv.discard and self.card_id not in inv.hand:
            inv.discard.append(self.card_id)
        game_state.log_effect(
            f"🛡️ 抵挡：【{game_state.card_name(enemy.card_id)}】攻击你后被自动躲避，"
            "且不能准备")
        return True

    @on_event(GameEvent.CARD_READIED, priority=TimingPriority.AFTER)
    def prevent_ready(self, ctx):
        """被叠加的敌人不能准备（准备后立即重新横置）。"""
        attached = ctx.game_state.scenario.vars.get("fend_off_attached", {})
        if ctx.target not in attached:
            return
        enemy = ctx.game_state.get_card_instance(ctx.target)
        if enemy is not None:
            enemy.exhausted = True
            ctx.game_state.log_effect(
                f"🛡️ 抵挡：【{ctx.game_state.card_name(enemy.card_id)}】不能准备")
