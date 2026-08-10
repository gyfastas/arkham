"""Tennessee Sour Mash (Level 0) — Rogue Asset. (05117)
使用(2补给)。
[fast] 消耗田纳西酸麦芽威士忌并花费1补给：你在诡计卡的一次技能检定中+2意志。
[action] 丢弃田纳西酸麦芽威士忌：攻击。你这次攻击+3战斗。

简化说明：
- 两个能力经 activations 公开方法实现（会话层 ACTIVATE_CARD 路由，同
  survivor 版 tennessee_sour_mash_lv3 模式）。
- "诡计卡的技能检定"无法从检定上下文识别（引擎缺口），近似为武装后持有者
  的下一次意志检定+2。
- 攻击能力沿用 shrivelling 模式：activate_fight() 丢弃本卡并武装，随后由
  会话层以 weapon_instance_id=本卡实例发起战斗。
- 数据中 uses 键为 "suppliess"（源数据笔误），按键名前缀兼容读取。
- 注意：data 中 rogue/tennessee_sour_mash_lv3.json(05190) 与
  survivor/tennessee_sour_mash_lv3.json(05191) 共用同一 card_id，注册表
  只能保留其一（数据层冲突，见批次报告）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.engine.slots import vacate_asset_slots
from backend.models.enums import GameEvent, Skill, TimingPriority


class TennesseeSourMashRogue(CardImplementation):
    card_id = "tennessee_sour_mash_lv0"
    willpower_bonus = 2  # lv3(05190) 为 +3
    combat_bonus = 3
    bonus_damage = 0     # lv3(05190) 为 +1
    activations = [
        {
            "id": "steady_nerves",
            "label": "消耗+1补给：下次意志检定+2",
            "method": "activate_willpower",
        },
        {
            "id": "brawl",
            "label": "丢弃：攻击+3战斗",
            "method": "activate_fight",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._willpower_armed = False
        self._fight_armed = False

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
        game_state.log_effect(
            f"🥃 田纳西酸麦芽威士忌：下次意志检定+{self.willpower_bonus}")
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
        game_state.log_effect(
            f"🥃 田纳西酸麦芽威士忌：丢弃，本次攻击+{self.combat_bonus}战斗")
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
            ctx.modify_amount(self.willpower_bonus, "tennessee_sour_mash_willpower")
        if (
            self._fight_armed
            and ctx.source == self.instance_id
            and ctx.skill_type == Skill.COMBAT
        ):
            ctx.modify_amount(self.combat_bonus, "tennessee_sour_mash_combat")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def fight_bonus_damage(self, ctx):
        if not self.bonus_damage:
            return
        if (
            self._fight_armed
            and ctx.source == self.instance_id
            and ctx.skill_type == Skill.COMBAT
        ):
            ctx.extra["bonus_damage"] = int(
                ctx.extra.get("bonus_damage", 0) or 0) + self.bonus_damage

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._willpower_armed = False
        self._fight_armed = False
