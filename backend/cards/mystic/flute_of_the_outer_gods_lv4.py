"""Flute of the Outer Gods (Level 4) — Mystic Asset, Hand slot. (07268)
卓越。封印（至多X个[curse]，X为混乱袋中的[curse]标记数——官方FAQ裁定）。
[action] 横置外神的长笛并释放其上封印的1个[curse]标记：选择你所在地点的
一个非[[精英]]敌人。将所选敌人移动到1个连接地点，或对所选敌人所在地点的
任一敌人造成等同于所选敌人伤害值的伤害。本行动不引发趁乱攻击。

简化说明：
- 入场封印经 CARD_ENTERS_PLAY 自动封印袋中全部[curse]标记（"至多X"取满）。
- activate() 公开方法由会话层调用：mode="move" 移动到首个连接地点（可传
  destination 指定）；mode="damage" 对目标敌人造成所选敌人伤害值的伤害
  （默认对所选敌人自身）。
- 伤害与击败结算复用 _shared.deal_damage_to_enemy（无事件总线可传，
  ENEMY_DEFEATED 不补发——引擎缺口，同 astral_travel 惯例）。
"""

from backend.cards._shared import deal_damage_to_enemy
from backend.cards.base import CardImplementation, on_event
from backend.models.enums import ChaosTokenType, GameEvent, TimingPriority


class FluteOfTheOuterGods(CardImplementation):
    card_id = "flute_of_the_outer_gods_lv4"
    activations = [{
        "id": "command",
        "label": "横置+释放1[curse]：移动非精英敌人或以其伤害值伤害敌人",
        "method": "activate",
        "actions": 1,
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._chaos_bag = None
        self._sealed_curses = 0

    def bind_chaos_bag(self, chaos_bag) -> None:
        self._chaos_bag = chaos_bag

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def seal_curses_on_enter(self, ctx):
        """入场：封印袋中全部[curse]标记（X=袋中[curse]数，取满）。"""
        if ctx.target != self.instance_id or self._chaos_bag is None:
            return
        while self._chaos_bag.seal_token(ChaosTokenType.CURSE):
            self._sealed_curses += 1
        if self._sealed_curses:
            ctx.extra["flute_sealed_curses"] = self._sealed_curses

    def activate(self, game_state, investigator_id: str,
                 enemy_instance_id: str,
                 mode: str = "move",
                 destination: str | None = None,
                 target_enemy_instance_id: str | None = None) -> bool:
        """横置并释放1个封印[curse]：移动或以其伤害值伤害敌人。"""
        inv = game_state.get_investigator(investigator_id)
        if inv is None:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        if inst is None or inst.exhausted or self._sealed_curses <= 0:
            return False
        enemy = game_state.get_card_instance(enemy_instance_id)
        enemy_data = game_state.get_card_data(enemy.card_id) if enemy else None
        if enemy is None or enemy_data is None:
            return False
        if "elite" in [t.lower() for t in (enemy_data.traits or [])]:
            return False
        # 敌人须在发动者所在地点（交战或在该地点）
        enemy_loc = self._enemy_location(game_state, enemy_instance_id)
        engaged = enemy_instance_id in inv.threat_area
        if not engaged and enemy_loc != inv.location_id:
            return False

        inst.exhausted = True
        self._sealed_curses -= 1
        if self._chaos_bag is not None:
            self._chaos_bag.release_token(ChaosTokenType.CURSE)

        if mode == "damage":
            target_iid = target_enemy_instance_id or enemy_instance_id
            amount = enemy_data.enemy_damage or 0
            deal_damage_to_enemy(game_state, None, target_iid, amount,
                                 defeated_by=investigator_id)
            return True

        # mode == "move"：移动到连接地点
        src_loc = game_state.get_location(enemy_loc or inv.location_id)
        dest = destination
        if dest is None and src_loc is not None and src_loc.connections:
            dest = src_loc.connections[0]
        dest_loc = game_state.get_location(dest) if dest else None
        if dest_loc is None:
            return True  # 无连接地点：效果仅释放标记（简化）
        if engaged:
            inv.threat_area.remove(enemy_instance_id)
        if src_loc is not None and enemy_instance_id in src_loc.enemies:
            src_loc.enemies.remove(enemy_instance_id)
        if enemy_instance_id not in dest_loc.enemies:
            dest_loc.enemies.append(enemy_instance_id)
        return True

    @staticmethod
    def _enemy_location(game_state, enemy_instance_id) -> str | None:
        for loc in game_state.locations.values():
            if enemy_instance_id in loc.enemies:
                return loc.location_id
        return None
