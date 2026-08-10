"""Sword Cane (Level 0) — Mystic Asset, Hand slot. (07029)
打出本卡不引起趁乱攻击。
[reaction] 在本卡入场后：立即触发其"[action]"能力，不支付其费用。
[action] 消耗本卡：攻击/躲避。本次攻击或躲避你可以使用[willpower]代替
[combat]或[agility]。

简化说明：
- 打出不引起趁乱攻击：ATTACK_OF_OPPORTUNITY 上下文不携带行动类型
  （引擎缺口，同 trench_knife），以"刚入场"标记近似：入场后的第一波
  趁乱攻击全部取消，下一次 ACTION_PERFORMED 清除标记。
- 入场反应简化为武装一次"免费启动"：随后本会话内由玩家发起的下一次
  战斗/躲避检定可用意志代替（官方为立即触发，由会话层选择目标与模式；
  未使用则在回合结束时过期）。
- 启动能力拆为 fight/evade 两个 activations（消耗本卡并武装对应技能）。
"""

from backend.cards.base import CardImplementation, on_event
from backend.models.enums import GameEvent, Skill, TimingPriority


class SwordCane(CardImplementation):
    card_id = "sword_cane_lv0"
    activations = [
        {
            "id": "fight",
            "label": "消耗：攻击（可用意志代替战斗）",
            "method": "activate_fight",
            "actions": 1,
            "target": "enemy",
        },
        {
            "id": "evade",
            "label": "消耗：躲避（可用意志代替敏捷）",
            "method": "activate_evade",
            "actions": 1,
            "target": "enemy",
        },
    ]

    def __init__(self, instance_id: str = "") -> None:
        super().__init__(instance_id)
        self._just_played = False
        self._free_armed = False       # 入场反应武装的免费启动
        self._free_consumed = False
        self._armed_skill: Skill | None = None

    @on_event(GameEvent.CARD_ENTERS_PLAY, priority=TimingPriority.AFTER)
    def on_enters_play(self, ctx):
        if ctx.target != self.instance_id:
            return
        self._just_played = True
        # 反应：立即触发启动能力（武装一次免费的意志代替，见 docstring）
        self._free_armed = True
        ctx.game_state.log_effect("🗡 剑杖：入场反应，立即触发一次免费启动")

    @on_event(GameEvent.ATTACK_OF_OPPORTUNITY, priority=TimingPriority.WHEN)
    def cancel_aoo(self, ctx):
        """打出本卡不引起趁乱攻击。"""
        if not self._just_played:
            return
        ctx.cancel()
        ctx.game_state.log_effect("🗡 剑杖：打出不引起趁乱攻击")

    @on_event(GameEvent.ACTION_PERFORMED, priority=TimingPriority.AFTER)
    def clear_just_played(self, ctx):
        self._just_played = False

    def _ready(self, game_state, investigator_id: str) -> bool:
        inv = game_state.get_investigator(investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return False
        inst = game_state.get_card_instance(self.instance_id)
        return inst is not None and not inst.exhausted

    def activate_fight(self, game_state, investigator_id: str,
                       target_instance_id: str | None = None) -> bool:
        """消耗：武装一次"可用意志代替战斗"的攻击。"""
        if not self._ready(game_state, investigator_id):
            return False
        game_state.get_card_instance(self.instance_id).exhausted = True
        self._armed_skill = Skill.COMBAT
        return True

    def activate_evade(self, game_state, investigator_id: str,
                       target_instance_id: str | None = None) -> bool:
        """消耗：武装一次"可用意志代替敏捷"的躲避。"""
        if not self._ready(game_state, investigator_id):
            return False
        game_state.get_card_instance(self.instance_id).exhausted = True
        self._armed_skill = Skill.AGILITY
        return True

    @on_event(GameEvent.SKILL_VALUE_DETERMINED, priority=TimingPriority.WHEN)
    def substitute_willpower(self, ctx):
        inv = ctx.game_state.get_investigator(ctx.investigator_id)
        if inv is None or self.instance_id not in inv.play_area:
            return
        applies = (
            ctx.skill_type == self._armed_skill
            or (self._free_armed and ctx.skill_type in (Skill.COMBAT, Skill.AGILITY))
        )
        if not applies:
            return
        base_val = inv.get_skill(ctx.skill_type)
        willpower = inv.get_skill(Skill.WILLPOWER)
        ctx.modify_amount(willpower - base_val, "sword_cane_substitute")
        if self._free_armed and ctx.skill_type != self._armed_skill:
            self._free_consumed = True

    @on_event(GameEvent.SKILL_TEST_ENDS, priority=TimingPriority.AFTER)
    def clear(self, ctx):
        self._armed_skill = None
        if self._free_consumed:
            self._free_armed = False
            self._free_consumed = False

    @on_event(GameEvent.ROUND_ENDS, priority=TimingPriority.AFTER)
    def expire_free_use(self, ctx):
        self._free_armed = False
        self._free_consumed = False
