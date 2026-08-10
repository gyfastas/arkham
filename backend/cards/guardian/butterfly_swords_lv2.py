"""Butterfly Swords (Level 2) — Guardian Asset, Hand x2. (08025)
[行动]：攻击。本次攻击你获得+1战斗。本次攻击后，你可以横置蝴蝶对剑再次攻击，
该次攻击你将敏捷加到技能值上。该次攻击造成+1伤害。

简化说明：
- 第一次攻击的 +1 战斗为武器被动（参照 machete，经 weapon_instance_id 识别）。
- "再次攻击"为第二次完整的战斗行动（费1行动）：经 fight_again 启动能力武装
  （需第一次攻击刚结束且本卡未横置），随后由会话层发起战斗行动；
  该次攻击经 SKILL_VALUE_DETERMINED 加入敏捷、成功时 +1 伤害。
- "攻击后"窗口：第一次攻击的 SKILL_TEST_ENDS 置位；以其他武器发起攻击或
  回合结束时窗口关闭。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class ButterflySwordsLv2(CardImplementation):
    card_id = "butterfly_swords_lv2"
    combat_bonus_amount = 1
    followup_requires_exhaust = True   # lv5 覆盖：再次攻击不需横置
    followup_bonus_damage = 1          # lv5 覆盖：见 lv5 规则
    activations = [{
        "id": "fight_again",
        "label": "横置：再次攻击（加敏捷，+1伤害）",
        "method": "activate_fight_again",
        "actions": 1,
        "target": "enemy",
    }]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._followup_ready = False      # 第一次攻击刚结束，可再次攻击
        self._followup_armed = False      # 已武装的追加攻击进行中
        self._first_attack_success = False  # lv5 用：第一次攻击是否成功

    # ------------------------------------------------------------------
    # 第一次攻击：+1 战斗（被动）
    # ------------------------------------------------------------------
    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def combat_bonus(self, ctx):
        if ctx.skill_type != Skill.COMBAT or ctx.source != self.instance_id:
            return
        ctx.modify_amount(self.combat_bonus_amount, "butterfly_swords_combat_bonus")
        if self._followup_armed:
            self._apply_followup_skill(ctx)

    def _apply_followup_skill(self, ctx):
        """追加攻击：将敏捷加到技能值上。"""
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is not None:
            agility = inv.get_skill(Skill.AGILITY)
            if agility:
                ctx.modify_amount(agility, "butterfly_swords_followup_agility")

    @on_event(GameEvent.SKILL_TEST_SUCCESSFUL, priority=TimingPriority.WHEN)
    def followup_success_bonus(self, ctx):
        if ctx.source != self.instance_id or ctx.skill_type != Skill.COMBAT:
            return
        if self._followup_armed:
            self._on_followup_success(ctx)

    def _on_followup_success(self, ctx):
        """lv2：追加攻击 +1 伤害（横置已在启动时支付）。"""
        if self.followup_bonus_damage:
            ctx.extra["bonus_damage"] = int(
                ctx.extra.get("bonus_damage", 0) or 0) + self.followup_bonus_damage
            ctx.extra["butterfly_swords_followup_bonus"] = True

    # ------------------------------------------------------------------
    # 追加攻击窗口
    # ------------------------------------------------------------------
    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def open_or_close_window(self, ctx):
        if ctx.source == self.instance_id and not self._followup_armed:
            # 第一次攻击刚结束：开放再次攻击窗口，记录是否成功（lv5 用）
            self._followup_ready = True
            self._first_attack_success = bool(ctx.success)
        self._followup_armed = False

    @on_event(GameEvent.FIGHT_ACTION_INITIATED, priority=TimingPriority.WHEN)
    def close_window_on_other_fight(self, ctx):
        """以其他武器发起攻击时，追加窗口关闭。"""
        if ctx.source != self.instance_id:
            self._followup_ready = False
            self._first_attack_success = False

    @on_event(GameEvent.INVESTIGATOR_TURN_ENDS, priority=TimingPriority.AFTER)
    def close_window_on_turn_end(self, ctx):
        self._followup_ready = False
        self._first_attack_success = False

    # ------------------------------------------------------------------
    # 启动能力：再次攻击
    # ------------------------------------------------------------------
    def activate_fight_again(self, game_state, investigator_id: str,
                             enemy_instance_id: str | None = None) -> bool:
        """（横置并）武装一次追加攻击；随后由会话层发起战斗行动。"""
        inv = game_state.get_investigator(investigator_id)
        inst = game_state.get_card_instance(self.instance_id)
        if inv is None or inst is None or self.instance_id not in inv.play_area:
            return False
        if not self._followup_ready:
            return False
        if self.followup_requires_exhaust and inst.exhausted:
            return False
        if self.followup_requires_exhaust:
            inst.exhausted = True
        self._followup_ready = False
        self._followup_armed = True
        game_state.log_effect("🦋 蝴蝶对剑：再次攻击（敏捷加入技能值）")
        return True
