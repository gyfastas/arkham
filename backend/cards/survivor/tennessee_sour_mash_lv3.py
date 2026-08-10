"""Tennessee Sour Mash (Level 3) — Survivor Asset. (05191)
使用(3补给)。
[fast] 消耗田纳西酸麦芽威士忌并花费1补给：你在诡计卡的一次技能检定中
+2 [willpower]。
[action] 丢弃田纳西酸麦芽威士忌：攻击。你这次攻击+3 [combat]。如果这次攻击
目标为一名非精英敌人并成功，自动躲避该敌人。

简化说明：
- 两个能力经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由）。
- "诡计卡的技能检定"无法从检定上下文识别（引擎缺口），近似为武装后持有者的
  下一次意志检定 +2（同 ResourceSkillBoost 的"下一次检定"口径）。
- 攻击能力沿用 shrivelling 模式：activate_fight() 丢弃本卡并武装，随后由
  会话层以 weapon_instance_id=本卡实例发起战斗；"目标敌人"取启动时传入的
  target（缺省自动选交战敌人）。攻击成功且目标非精英时自动躲避
  （横置+脱离+放置于地点，不发 ENEMY_EVADED，同 cunning_distraction 从简）；
  敌人已被击败离场则不再躲避。
- 数据中 uses 键为 "suppliess"（源数据笔误），按键名前缀兼容读取。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority
from backend.scenarios.official_core import is_elite_enemy


class TennesseeSourMash(CardImplementation):
    card_id = "tennessee_sour_mash_lv3"
    activations = [
        {
            "id": "steady_nerves",
            "label": "消耗+1补给：下次意志检定+2",
            "method": "activate_willpower",
        },
        {
            "id": "brawl",
            "label": "丢弃：攻击+3战斗，成功则自动躲避非精英敌人",
            "method": "activate_fight",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._willpower_armed = False
        self._fight_armed = False
        self._target: str | None = None

    # ------------------------------------------------------------------
    # 启动能力
    # ------------------------------------------------------------------
    def activate_willpower(self, game_state, investigator_id: str) -> bool:
        """[fast] 消耗+花费1补给：下一次意志检定+2。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or inst.exhausted:
            return False
        if self.instance_id not in inv.play_area:
            return False
        key = self._uses_key(inst)
        if key is None or inst.uses.get(key, 0) < 1:
            return False
        inst.uses[key] -= 1
        inst.exhausted = True
        self._willpower_armed = True
        game_state.log_effect("🥃 田纳西酸麦芽威士忌：下次意志检定+2")
        return True

    def activate_fight(
        self, game_state, investigator_id: str, enemy_instance_id: str | None = None
    ) -> bool:
        """[action] 丢弃本卡：攻击+3战斗（武装后由会话层发起战斗）。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None:
            return False
        if self.instance_id not in inv.play_area:
            return False

        # 丢弃本卡（费用）
        vacate_asset_slots(game_state, self.instance_id)
        inv.play_area.remove(self.instance_id)
        game_state.cards_in_play.pop(self.instance_id, None)
        inv.discard.append(self.card_id)

        self._fight_armed = True
        self._target = enemy_instance_id
        game_state.log_effect("🥃 田纳西酸麦芽威士忌：丢弃，本次攻击+3战斗")
        return True

    @staticmethod
    def _uses_key(inst) -> str | None:
        """补给键（兼容源数据笔误 "suppliess"）。"""
        return next((k for k in inst.uses if k.startswith("supplies")), None)

    # ------------------------------------------------------------------
    # 检定钩子
    # ------------------------------------------------------------------
    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def apply_bonuses(self, ctx):
        if self._willpower_armed and ctx.skill_type == Skill.WILLPOWER:
            ctx.modify_amount(2, "tennessee_sour_mash_willpower")
        if (
            self._fight_armed
            and ctx.source == self.instance_id
            and ctx.skill_type == Skill.COMBAT
        ):
            ctx.modify_amount(3, "tennessee_sour_mash_combat")

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def resolve_and_clear(self, ctx):
        try:
            if (
                self._fight_armed
                and ctx.source == self.instance_id
                and ctx.success
            ):
                self._auto_evade(ctx)
        finally:
            self._willpower_armed = False
            self._fight_armed = False
            self._target = None

    def _auto_evade(self, ctx) -> None:
        """攻击成功且目标非精英：自动躲避。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None:
            return
        enemy_iid = self._target
        enemy = ctx.game_state.get_card_instance(enemy_iid) if enemy_iid else None
        if enemy is None:
            # 缺省：交战且准备好的第一个敌人
            for iid in inv.threat_area:
                cand = ctx.game_state.get_card_instance(iid)
                if cand is not None and not cand.exhausted:
                    enemy_iid, enemy = iid, cand
                    break
        if enemy is None:
            return  # 敌人已被击败离场
        cd = ctx.game_state.get_card_data(enemy.card_id)
        if cd is not None and is_elite_enemy(cd):
            return

        enemy.exhausted = True
        for other in ctx.game_state.investigators.values():
            if enemy_iid in other.threat_area:
                other.threat_area.remove(enemy_iid)
        loc = ctx.game_state.get_location(inv.location_id)
        if loc is not None and enemy_iid not in loc.enemies:
            loc.enemies.append(enemy_iid)
        ctx.extra["tennessee_sour_mash_evaded"] = enemy_iid
        ctx.game_state.log_effect(
            f"🥃 田纳西酸麦芽威士忌：自动躲避【{ctx.game_state.card_name(enemy.card_id)}】")
